"""Offline summaries of saved resource-planning attempts; never reruns a solver.

The experiment manifest defines the denominator, including missing/interrupted
attempts. Bootstrap resampling is over targets, retaining all paired policy
seeds within each sampled target. Private targets are not copied into reports.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import random
from statistics import mean, median
from xml.etree import ElementTree as ET

from budgeted_science.agents.records import json_text, read_events


POLICIES = ("random", "adaptive")
METRICS = ("score", "success", "parameter_error", "credits_spent", "elapsed_seconds")


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _inside(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("saved artifact path escapes the run directory")
    return path


def load_attempts(path):
    """Load canonical results, falling back to finalized events after interruption.

    Source records are never changed. A missing outcome is an explicit failure,
    not an invented estimate or a silently dropped observation.
    """
    path = Path(path).resolve()
    manifest = _read_json(path / "manifest.json")
    events, torn = read_events(path)
    finished = {}
    started = set()
    for event in events:
        if event["kind"] == "attempt_started":
            started.add(event["attempt_id"])
        elif event["kind"] == "attempt_finished":
            result = event["result"]
            if result["attempt_id"] in finished:
                raise ValueError("duplicate finalized attempt in chronology")
            finished[result["attempt_id"]] = result
    rows, seen = [], set()
    for spec in manifest["attempts"]:
        identity = {key: spec[key] for key in
                    ("attempt_id", "target_id", "target_seed", "policy_seed", "policy")}
        key = identity["attempt_id"]
        if key in seen:
            raise ValueError("duplicate attempt in manifest")
        seen.add(key)
        result_path = _inside(path, spec["result_path"])
        result = _read_json(result_path) if result_path.exists() else finished.get(key)
        if result is None:
            result = {**identity, "status": "interrupted_without_result" if key in started else "not_started",
                      "started": key in started, "success": False, "valid": False,
                      "parameter_error": None, "resources": {}, "elapsed_seconds": None}
        elif any(result.get(k) != v for k, v in identity.items()):
            raise ValueError(f"result identity does not match manifest: {key}")
        if key in finished and result != finished[key]:
            raise ValueError(f"result and chronology disagree: {key}")
        rows.append(result)
    if set(finished) - seen:
        raise ValueError("chronology contains an unplanned attempt")
    return manifest, rows, {"torn_final_event": torn,
                            "experiment_finished": any(e["kind"] == "experiment_finished" for e in events)}


def _valid(row):
    return row.get("status") == "completed" and row.get("valid") is True and finite(row.get("parameter_error"))


def _metric(row, metric):
    if metric == "score":
        return float(_valid(row) and row.get("success") is True)
    if metric == "success":
        return float(_valid(row) and row.get("success") is True)
    if metric == "parameter_error":
        return float(row[metric]) if _valid(row) else None
    if metric == "credits_spent":
        value = row.get("resources", {}).get(metric)
    else:
        value = row.get(metric)
    return float(value) if finite(value) else None


def _distribution(values):
    values = [float(v) for v in values if finite(v)]
    return {"count": len(values), "mean": mean(values) if values else None,
            "median": median(values) if values else None,
            "minimum": min(values) if values else None,
            "maximum": max(values) if values else None,
            "total": sum(values) if values else None}


def _quantile(values, q):
    ordered = sorted(values)
    index = (len(ordered) - 1) * q
    low = math.floor(index)
    high = math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def paired_bootstrap(rows, *, repetitions=2000, seed=0, policy_seeds=None):
    """Percentile intervals for adaptive-minus-random means.

    Resample whole target clusters with replacement. Each draw keeps every seed
    and both methods, including failed attempts. Error/resource differences use
    only pairs with both values observed; missingness is counted explicitly.
    Undefined bootstrap replicates are retained as a count, never set to zero.
    """
    if isinstance(repetitions, bool) or not isinstance(repetitions, int) or repetitions < 1:
        raise ValueError("bootstrap repetitions must be a positive integer")
    grouped = defaultdict(dict)
    for row in rows:
        if row["policy"] not in POLICIES:
            raise ValueError("unknown policy in saved results")
        key = (row["policy_seed"], row["policy"])
        if key in grouped[row["target_id"]]:
            raise ValueError("duplicate target/policy/seed result")
        grouped[row["target_id"]][key] = row
    seeds = sorted(set(policy_seeds) if policy_seeds is not None else {r["policy_seed"] for r in rows})
    expected = {(s, p) for s in seeds for p in POLICIES}
    if any(set(group) != expected for group in grouped.values()):
        raise ValueError("each target must retain every paired policy seed; use the saved manifest to fill missing attempts")
    target_ids = sorted(grouped)
    clusters = {metric: [] for metric in METRICS}
    for target in target_ids:
        for metric in METRICS:
            differences = []
            for policy_seed in seeds:
                baseline = _metric(grouped[target][policy_seed, "random"], metric)
                adaptive = _metric(grouped[target][policy_seed, "adaptive"], metric)
                if baseline is not None and adaptive is not None:
                    differences.append(adaptive - baseline)
            clusters[metric].append(differences)
    rng = random.Random(seed)
    draws = {metric: [] for metric in METRICS}
    for _ in range(repetitions):
        indices = [rng.randrange(len(target_ids)) for _ in target_ids]
        for metric in METRICS:
            values = [value for i in indices for value in clusters[metric][i]]
            if values:
                draws[metric].append(mean(values))
    metrics = {}
    for metric in METRICS:
        values = [value for cluster in clusters[metric] for value in cluster]
        samples = draws[metric]
        metrics[metric] = {"difference": mean(values) if values else None,
                           "ci95": [_quantile(samples, .025), _quantile(samples, .975)] if samples else None,
                           "paired_observations": len(values),
                           "missing_pairs": len(target_ids) * len(seeds) - len(values),
                           "contributing_targets": sum(bool(c) for c in clusters[metric]),
                           "valid_bootstrap_replicates": len(samples),
                           "undefined_bootstrap_replicates": repetitions - len(samples)}
    return {"direction": "adaptive minus random", "unit": "target", "targets": len(target_ids),
            "policy_seeds_retained": seeds, "repetitions": repetitions, "seed": seed,
            "method": "paired target-cluster percentile bootstrap; observed paired values only",
            "metrics": metrics}


def summarize(rows, *, repetitions=2000, seed=0, policy_seeds=None):
    rows = list(rows)
    summary = {"schema_version": 1, "attempts": len(rows), "policies": {},
               "interpretation": "Primary score is binary success: every normalized parameter error must be at most one. "
               "Success rate uses every planned attempt; failures contribute zero. "
               "Primary parameter error is the MAXIMUM of the three absolute errors divided by tolerance times true parameter. "
               "Error uses valid completed submissions only. "
               "Resource and runtime statistics include observed failures and state their available counts. "
               "Paired error comparisons are conditional on both methods producing valid submissions."}
    for policy in POLICIES:
        subset = [r for r in rows if r["policy"] == policy]
        failures = Counter()
        for row in subset:
            if _metric(row, "success"):
                continue
            reason = row.get("status", "missing_status")
            if reason == "completed":
                reason = "tolerance_not_met" if _valid(row) else "invalid_or_missing_submission"
            failures[reason] += 1
        resource_keys = sorted({key for row in subset for key, value in row.get("resources", {}).items()
                                if finite(value)})
        successes = sum(int(_metric(r, "success")) for r in subset)
        summary["policies"][policy] = {
            "attempts": len(subset), "started": sum(r.get("started", True) for r in subset),
            "completed": sum(r.get("status") == "completed" for r in subset),
            "valid_submissions": sum(_valid(r) for r in subset), "successes": successes,
            "mean_score_all_attempts": mean(_metric(r, "score") for r in subset) if subset else None,
            "success_rate_all_attempts": successes / len(subset) if subset else None,
            "parameter_error_valid_only": _distribution(_metric(r, "parameter_error") for r in subset),
            "parameter_errors_valid_only": [_distribution(
                r.get("parameter_errors", [None] * 3)[index] for r in subset if _valid(r)) for index in range(3)],
            "objective_success_rates_all_attempts": [
                sum(bool(r.get("objective_successes", [False] * 3)[index]) and _valid(r) for r in subset) / len(subset)
                if subset else None for index in range(3)],
            "elapsed_seconds": _distribution(_metric(r, "elapsed_seconds") for r in subset),
            "resources": {key: _distribution(r.get("resources", {}).get(key) for r in subset) for key in resource_keys},
            "failure_counts": dict(sorted(failures.items())),
        }
    summary["paired_bootstrap"] = paired_bootstrap(rows, repetitions=repetitions, seed=seed, policy_seeds=policy_seeds)
    return summary


def _number(value):
    return "unavailable" if value is None else f"{value:.6g}"


def markdown(summary):
    lines = ["# CPU resource-planning experiment", "", summary["interpretation"], "",
             f"Phase: {summary.get('phase', 'unspecified')}. Planned attempts: {summary['attempts']}.", "",
             "| Policy | Attempts | Valid | Mean binary score | Successes | Success rate | Mean valid worst error | Mean seconds (n) |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for policy, result in summary["policies"].items():
        runtime = result["elapsed_seconds"]
        lines.append(f"| {policy} | {result['attempts']} | {result['valid_submissions']} | "
                     f"{_number(result['mean_score_all_attempts'])} | {result['successes']} | "
                     f"{_number(result['success_rate_all_attempts'])} | {_number(result['parameter_error_valid_only']['mean'])} | "
                     f"{_number(runtime['mean'])} ({runtime['count']}) |")
    lines += ["", "## Resources and failures", ""]
    for policy, result in summary["policies"].items():
        lines += [f"### {policy}", "", "| Resource | Available n | Mean | Total |", "|---|---:|---:|---:|"]
        for key, values in result["resources"].items():
            lines.append(f"| {key} | {values['count']} | {_number(values['mean'])} | {_number(values['total'])} |")
        lines += ["", "Failure counts: " + (", ".join(f"{k}: {v}" for k, v in result["failure_counts"].items()) or "none") + ".", ""]
    paired = summary["paired_bootstrap"]
    lines += ["## Paired uncertainty", "",
              f"Adaptive minus random; {paired['repetitions']} bootstrap draws (seed {paired['seed']}) over "
              f"{paired['targets']} targets. Each target keeps policy seeds {paired['policy_seeds_retained']} together.", "",
              "| Metric | Mean difference | 95% percentile interval | Observed pairs | Missing pairs | Undefined draws |",
              "|---|---:|---|---:|---:|---:|"]
    for key, result in paired["metrics"].items():
        interval = "unavailable" if result["ci95"] is None else " to ".join(_number(v) for v in result["ci95"])
        lines.append(f"| {key} | {_number(result['difference'])} | {interval} | {result['paired_observations']} | "
                     f"{result['missing_pairs']} | {result['undefined_bootstrap_replicates']} |")
    if summary.get("recovery", {}).get("torn_final_event"):
        lines += ["", "Warning: the final event line is torn; the saved source was preserved."]
    if not summary.get("recovery", {}).get("experiment_finished", True):
        lines += ["", "The experiment has no final completion event. Missing outcomes remain explicit failures."]
    lines += ["", "Plots show paired target means using observed matched seeds; sample counts are in the JSON report.", "",
              "![Paired valid parameter errors](paired_errors.svg)", "",
              "![Paired resource consumption](paired_resources.svg)", "",
              "Numerical diagnostics and full chronology remain in the saved attempt artifacts. "
              "These toy results do not establish general planning ability.", ""]
    return "\n".join(lines)


def _paired_plot(rows, metric, title):
    """Small scientific SVG, without optional plotting dependencies or raster assets."""
    ns = "http://www.w3.org/2000/svg"
    ET.register_namespace("", ns)
    root = ET.Element(f"{{{ns}}}svg", {"viewBox": "0 0 680 440", "role": "img"})
    def element(tag, **attributes):
        return ET.SubElement(root, f"{{{ns}}}{tag}", {k.replace('_', '-'): str(v) for k, v in attributes.items()})
    element("title").text = title
    element("rect", width=680, height=440, fill="white")
    element("text", x=340, y=30, text_anchor="middle", font_family="sans-serif", font_size=18).text = title
    grouped = defaultdict(dict)
    for row in rows:
        grouped[row["target_id"]][row["policy_seed"], row["policy"]] = _metric(row, metric)
    points = []
    for target, group in sorted(grouped.items()):
        pairs = [(group.get((seed, "random")), group.get((seed, "adaptive")))
                 for seed in sorted({s for s, _ in group})]
        pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
        if pairs:
            points.append((target, mean(a for a, _ in pairs), mean(b for _, b in pairs), len(pairs)))
    maximum = max((max(a, b) for _, a, b, _ in points), default=1) * 1.08 or 1
    x0, y0, width, height = 90, 365, 490, 290
    for i in range(6):
        value = maximum * i / 5
        x, y = x0 + width * i / 5, y0 - height * i / 5
        element("line", x1=x0, x2=x0 + width, y1=y, y2=y, stroke="#e5e7eb")
        element("text", x=x, y=y0 + 21, text_anchor="middle", font_family="sans-serif", font_size=11).text = f"{value:.3g}"
        element("text", x=x0 - 10, y=y + 4, text_anchor="end", font_family="sans-serif", font_size=11).text = f"{value:.3g}"
    element("line", x1=x0, x2=x0 + width, y1=y0, y2=y0 - height, stroke="#777", stroke_dasharray="5 4")
    element("line", x1=x0, x2=x0 + width, y1=y0, y2=y0, stroke="#222")
    element("line", x1=x0, x2=x0, y1=y0, y2=y0 - height, stroke="#222")
    for target, a, b, n in points:
        point = element("circle", cx=x0 + width * a / maximum, cy=y0 - height * b / maximum,
                        r=4.5, fill="#2166ac", fill_opacity=.7)
        ET.SubElement(point, f"{{{ns}}}title").text = f"{target}: random={a:.8g}, adaptive={b:.8g}, paired seeds={n}"
    element("text", x=340, y=422, text_anchor="middle", font_family="sans-serif", font_size=14).text = "Random: paired target mean"
    element("text", x=22, y=225, transform="rotate(-90 22 225)", text_anchor="middle",
            font_family="sans-serif", font_size=14).text = "Adaptive: paired target mean"
    element("text", x=340, y=54, text_anchor="middle", font_family="sans-serif", font_size=12).text = (
        f"{len(points)} targets with observed pairs; dashed line: equality" if points else "No valid paired observations")
    return ET.tostring(root, encoding="unicode") + "\n"


def regenerate(path, *, output_dir=None, repetitions=2000, seed=0):
    """Write derived JSON/Markdown/SVG using only saved results and events."""
    path = Path(path).resolve()
    manifest, rows, recovery = load_attempts(path)
    report = summarize(rows, repetitions=repetitions, seed=seed, policy_seeds=manifest.get("policy_seeds"))
    report.update(phase=manifest["phase"], recovery=recovery,
                  provenance={key: manifest.get(key) for key in ("source_hashes", "versions", "freeze_digest")})
    destination = Path(output_dir).resolve() if output_dir else path / "report"
    # Derived artifacts must not overwrite canonical source records.
    if destination == path or destination.is_relative_to(path / "attempts"):
        raise ValueError("report output must be separate from canonical run records")
    destination.mkdir(parents=True, exist_ok=True)
    artifacts = {"summary.json": json_text(report) + "\n", "report.md": markdown(report),
                 "paired_errors.svg": _paired_plot(rows, "parameter_error", "Worst normalized parameter error"),
                 "paired_resources.svg": _paired_plot(rows, "credits_spent", "Scientific credits consumed")}
    for name, content in artifacts.items():
        (destination / name).write_text(content, encoding="utf-8", newline="\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--bootstrap-repetitions", type=int, default=2000)
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    args = parser.parse_args(argv)
    result = regenerate(args.run, output_dir=args.output_dir,
                        repetitions=args.bootstrap_repetitions, seed=args.bootstrap_seed)
    print(json_text({"attempts": result["attempts"], "report_directory": str(args.output_dir or args.run / "report")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
