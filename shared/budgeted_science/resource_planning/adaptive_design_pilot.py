"""CPU-only development, frozen five-case comparison, and offline regeneration."""

import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from budgeted_science.agents.records import RunLog, digest, read_events
from .adaptive_design import NAME, SETTINGS, run_adaptive_design
from .config import harder_config
from .environment import Episode
from .experiment import REPO, source_hashes, versions


CASES = (6000, 6020, 6021, 6022, 6023)
DEVELOPMENT = tuple(range(5000, 5008))
COMPARISON = REPO / "demos/planning/runs/resource_terra_five_case/20260911T200237Z-prepared-cabe9f2088/summary.json"
OUTPUT = REPO / "demos/planning/runs/adaptive_multifidelity_design"
METHODS = ("local", "adaptive", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna")


def read_comparisons(path=COMPARISON):
    """Private reporting side only. The design policy never receives these rows."""
    path = Path(path)
    payload = path.read_bytes()
    saved = json.loads(payload)
    if not saved["complete"] or saved.get("rehearsal"):
        raise ValueError("comparison must be a completed, non-rehearsal campaign")
    rows = [r for r in saved["rows"] if r["method"] in METHODS and r["case_seed"] in CASES]
    if {(r["case_seed"], r["method"]) for r in rows} != {(s, m) for s in CASES for m in METHODS} or len(rows) != 25:
        raise ValueError("missing or duplicated saved comparisons")
    config = harder_config(32)
    bounds = np.array(config.bounds)
    for row in rows:
        theta = np.random.default_rng(row["case_seed"]).uniform(bounds[:, 0], bounds[:, 1])
        if row["noise_replicate"] != 0 or not np.array_equal(theta, row["evaluation"]["theta_true"]):
            raise ValueError("saved target/noise identity mismatch")
    return rows, {"path": str(path), "sha256": hashlib.sha256(payload).hexdigest()}


def verify_pair(public_evidence, saved_rows, seed):
    expected = next(r for r in saved_rows if r["case_seed"] == seed and r["method"] == "gpt-5.6-sol")
    observations = expected["evaluation"]["scientific_status"]["observations"]
    expected_initial = {(r["variable"], r["time"]): r["value"] for r in observations if r["time"] in (0, 1)}
    actual = {(r["variable"], r["time"]): r["value"] for r in public_evidence["observations"]}
    if expected_initial != actual:
        raise ValueError("initial noisy evidence does not match the saved agent case")


def run_case(seed, root, comparisons=()):
    log = RunLog(root / "episodes", str(seed))
    config = harder_config(32)
    bounds = np.array(config.bounds)
    theta = np.random.default_rng(seed).uniform(bounds[:, 0], bounds[:, 1])
    log.write_json("manifest.json", {"method": NAME, "case_seed": seed, "noise_replicate": 0,
                                    "PRIVATE_instance": {"theta": theta.tolist(), "noise_seed": seed * 10},
                                    "public_configuration": config.public(), "settings": SETTINGS})
    def emit(kind, **data):
        for field in ("artifact", "target_artifact"):
            if data.get(field) is not None:
                data[field + "_path"] = log.write_json(
                    f"numerical/{log._sequence + 1:06d}-{field}.json", data.pop(field))
        log.event(kind, **data)
    started = time.monotonic()
    episode, details, reason = None, None, "failed"
    try:
        episode = Episode(theta, config, log=emit, noise_seed=seed * 10)
        if comparisons:
            verify_pair(episode.tools.evidence(), comparisons, seed)
        details = run_adaptive_design(episode.tools, seed=0, log=emit,
                                     deadline=started + SETTINGS["episode_seconds"])
        reason = "submitted"
    except Exception as exc:
        emit("failure", error=log.redactor.error(exc))
        if episode:
            episode.abort(type(exc).__name__)
        reason = "timeout" if isinstance(exc, TimeoutError) else "failed"
    status = episode.tools.get_status() if episode else None
    result = {"case_seed": seed, "method": NAME, "noise_replicate": 0, "path": str(log.path),
              "termination": reason, "evaluation": episode.evaluate() if episode else None,
              "scientific_status": status, "details": details,
              "elapsed_seconds": time.monotonic() - started, "api_cost_usd": 0}
    if status:
        counts = {name: sum(e["kind"] == action for e in status["ledger"])
                  for name, action in (("low", "simulate_low"), ("high", "simulate_high"), ("measurement", "measure_target"))}
        result["resource_counts"] = counts
        expected_spent = counts["low"] + 8 * counts["high"] + 12 * counts["measurement"]
        result["accounting_valid"] = expected_spent == status["spent"] <= 32
        if not result["accounting_valid"]:
            raise RuntimeError("scientific accounting mismatch")
    log.write_json("result.json", result)
    log.event("episode_finished", result=result)
    log.close()
    return result


def aggregate(rows):
    groups = []
    for method in dict.fromkeys(r["method"] for r in rows):
        selected = [r for r in rows if r["method"] == method]
        valid = [r for r in selected if r.get("evaluation") and r["evaluation"]["valid"]]
        errors = [r["evaluation"]["parameter_error"] * .05 for r in valid]
        groups.append({"method": method, "attempts": len(selected),
                       "successes": sum(r["evaluation"]["success"] for r in valid),
                       "incomplete": len(selected) - len(valid),
                       "median_max_relative_error": float(np.median(errors)) if errors else None,
                       "mean_max_relative_error": float(np.mean(errors)) if errors else None})
    return groups


def render(root):
    """Saved logs only: does not construct an environment or call a policy."""
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text())
    events, torn = read_events(root)
    rows = [e["result"] for e in events if e["kind"] == "result"]
    saved = json.loads((root / "saved_comparisons.json").read_text())
    summary = {"phase": manifest["phase"], "rows": rows, "groups": aggregate(rows + saved),
               "complete": not torn and bool(events) and events[-1]["kind"] == "finished"
                           and events[-1].get("source_unchanged", True)
                           and len(rows) == len(manifest.get("cases", rows)),
               "comparison_source": manifest.get("comparison_source")}
    (root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    lines = ["# Adaptive multifidelity design", "", f"Phase: {manifest['phase']}.", "",
             "| Method | Pass / attempts | Median max error | Mean max error | Incomplete |",
             "|---|---:|---:|---:|---:|"]
    for g in summary["groups"]:
        fmt = lambda v: "n/a" if v is None else f"{100*v:.4f}%"
        lines.append(f"| {g['method']} | {g['successes']}/{g['attempts']} | {fmt(g['median_max_relative_error'])} | {fmt(g['mean_max_relative_error'])} | {g['incomplete']} |")
    lines += ["", "| Case | Submitted parameters | Per-parameter relative errors | Largest error | Pass | Low/high/measurement | Credits | Seconds |",
              "|---:|---|---|---:|---|---|---:|---:|"]
    for row in rows:
        ev = row["evaluation"]
        errors = [5*x for x in ev["errors"]] if ev and ev["valid"] else None
        lines.append(f"| {row['case_seed']} | {ev['theta_hat'] if ev else None} | {errors} % | {max(errors) if errors else None} % | {ev['success'] if ev else False} | {row.get('resource_counts')} | {row['scientific_status']['spent'] if row['scientific_status'] else None} | {row['elapsed_seconds']:.2f} |")
        episode_events, _ = read_events(Path(row["path"]))
        trace = [e for e in episode_events if e["kind"] == "adaptive_design_acquired"]
        trace_lines = ["# Complete acquisition trace", "", "| Step | Action | Location | Cost | Remaining | Estimated gain / credit |",
                       "|---:|---|---|---:|---:|---:|"]
        for e in trace:
            action = e["action"]
            location = action.get("theta", [action.get("variable"), action.get("time")])
            trace_lines.append(f"| {e['step']+1} | {action.get('fidelity', 'measurement')} | {location} | {e['result'].get('charge')} | {e['result'].get('remaining')} | {action['score']:.8g} |")
        (Path(row["path"]) / "trace.md").write_text("\n".join(trace_lines) + "\n", encoding="utf-8")
    lines += ["", "## Logs", ""]
    lines += [f"- Case {r['case_seed']}: [{r['path']}/trace.md]({Path(r['path']).as_posix()}/trace.md)" for r in rows]
    lines += ["", "Errors are relative percentages, not tolerance-normalized scores. Passing requires all three <=5%.",
              "This is a new method compared on reused pilot systems, not a new held-out benchmark.",
              "The covariance and action values are approximations, not certified confidence or optimal allocation.",
              "No LLM experiments were rerun; all model comparisons were imported.", ""]
    (root / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def campaign(phase, freeze=None, output=OUTPUT):
    sources, runtime = source_hashes(), versions()
    config = harder_config(32).public()
    saved, comparison = ([], None)
    if phase == "pilot":
        lock = json.loads((Path(freeze) / "freeze.json").read_text())
        if lock != {"source_hashes": sources, "settings": SETTINGS, "versions": runtime, "config": config}:
            raise ValueError("code/settings/runtime changed after development; run development again")
        saved, comparison = read_comparisons()
    root = RunLog(output, phase)
    root.write_json("manifest.json", {"phase": phase, "settings": SETTINGS, "source_hashes": sources,
                                     "versions": runtime, "config": config, "cases": CASES if phase == "pilot" else DEVELOPMENT,
                                     "comparison_source": comparison, "development": str(freeze) if freeze else None})
    root.write_json("saved_comparisons.json", saved)
    root.event("started", phase=phase)
    for seed in (CASES if phase == "pilot" else DEVELOPMENT):
        result = run_case(seed, root.path, saved)
        root.event("result", result=result)
        ev = result["evaluation"]
        print(seed, result["termination"], "max_relative_error=", ev["parameter_error"] * .05 if ev and ev["valid"] else None,
              "purchases=", result.get("resource_counts"), flush=True)
    unchanged = sources == source_hashes()
    root.event("finished", source_unchanged=unchanged)
    if not unchanged:
        raise RuntimeError("source changed during campaign")
    summary = render(root.path)
    if phase == "development" and not any(g["incomplete"] for g in summary["groups"]):
        root.write_json("freeze.json", {"source_hashes": sources, "settings": SETTINGS, "versions": runtime, "config": config})
    root.close()
    print(root.path, flush=True)
    return root.path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("development", "pilot", "render"))
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    if args.mode == "render":
        if not args.run:
            parser.error("render needs --run")
        render(args.run)
    else:
        if args.mode == "pilot" and not args.freeze:
            parser.error("pilot needs --freeze DEVELOPMENT_DIRECTORY")
        campaign(args.mode, args.freeze, args.output)


if __name__ == "__main__":
    main()
