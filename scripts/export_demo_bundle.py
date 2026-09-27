"""Maintainer-only export from existing local archives; never calls an API.

Uses an explicit allowlist of numerical results, case definitions, frozen task
prompts and schemas. Does not open credential files or copy API archives.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PLAN = "demos/planning/runs/adaptive_multifidelity_design/20260914T030431Z-pilot-c80fc4e963"
VERIFY = "demos/paired_claim_audit/runs/20260914T033437Z-adaptive-target-three-cpu-77c1fae6be"
CATALOG = "demos/paired_claim_audit/runs/20260913T085926Z-target-three-prepared-cdb738cbfa/catalog.json"
LUNA = "demos/paired_claim_audit/runs/20260913T105527Z-target-three-luna-case4-retry-live-90354c03ce/retry_inclusive_six_case_view.json"
MODELS = ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna")
BASELINE = "adaptive_multifidelity_design"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--output-root", type=Path, default=ROOT)
    args = parser.parse_args()
    source, output = args.source_root.resolve(), args.output_root.resolve()
    sources, exports = {}, {}

    def read(relative):
        path = (source / relative).resolve()
        # Only archived, explicitly selected run files; never arbitrary paths.
        path.relative_to(source / "demos")
        if path.name not in {"summary.json", "saved_comparisons.json", "catalog.json",
                             "retry_inclusive_six_case_view.json", "manifest.json",
                             "prompts.json", "tools.json"}:
            raise ValueError("unexpected source filename")
        data = path.read_bytes()
        sources[path.relative_to(source).as_posix()] = hashlib.sha256(data).hexdigest()
        return json.loads(data)

    def write(relative, obj):
        def strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, dict):
                for key, item in value.items():
                    yield str(key)
                    yield from strings(item)
            elif isinstance(value, list):
                for item in value:
                    yield from strings(item)
        # Check actual strings, not JSON escapes (e.g. "x:\n" is not a drive).
        pattern = r"\bsk-(?:proj-)?[A-Za-z0-9_-]{25,}|Bearer\s+\S+|(?<![A-Za-z])[A-Za-z]:[\\/]"
        if any(re.search(pattern, s) for s in strings(obj)):
            raise ValueError("unexpected credential-like string or absolute local path in " + relative)
        data = (json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        exports[relative] = hashlib.sha256(data).hexdigest()

    def method(row):
        return row["method"].split(" (")[0]

    def episode_path(row):
        # Archived Windows paths are mapped into the selected source tree.
        tail = row["path"].replace("\\", "/").split("/demos/", 1)[1]
        return "demos/" + tail

    def counts(status):
        names = {"low": "simulate_low", "high": "simulate_high", "measurement": "measure_target"}
        return {k: sum(e["kind"] == v for e in status["ledger"]) for k, v in names.items()}

    ps, vs = read(PLAN + "/summary.json"), read(VERIFY + "/summary.json")
    assert ps["complete"] and vs["complete"]
    prows = ps["rows"] + [r for r in read(PLAN + "/saved_comparisons.json") if method(r) in MODELS]
    vrows = vs["rows"] + [r for r in read(VERIFY + "/saved_comparisons.json") if method(r) in MODELS]
    assert len(prows) == 20 and len(vrows) == 24
    catalog, retry = read(CATALOG), read(LUNA)
    planning, verification, planning_cases, prompts, schemas = [], [], [], [], {}
    for row in prows:
        ev = row["evaluation"]
        status = row.get("scientific_status", ev.get("scientific_status"))
        errors = [abs(a-b)/abs(b) for a, b in zip(ev["theta_hat"], ev["theta_true"])]
        assert ev["valid"] and ev["success"] == (max(errors) <= .05)
        planning.append({
            "case_id": str(row["case_seed"]), "method": method(row),
            "theta_hat": ev["theta_hat"], "relative_errors": errors,
            "max_relative_error": max(errors), "success": ev["success"],
            "completed": True, "scientific_credits": status["spent"],
            "purchases": counts(status), "elapsed_seconds": row["elapsed_seconds"],
            "source_episode": episode_path(row),
        })
        if method(row) == BASELINE:
            # Initial evidence comes from the paired saved Sol result.
            paired = next(r for r in prows if r["case_seed"] == row["case_seed"] and method(r) == MODELS[0])
            evidence = paired["evaluation"]["scientific_status"]["observations"]
            planning_cases.append({
                "case_seed": row["case_seed"], "noise_replicate": 0,
                "noise_seed": 10*row["case_seed"], "theta_true": ev["theta_true"],
                "initial_observations": [x for x in evidence if x["time"] in (0, 1)],
            })
    for row in vrows:
        ev = row["evaluation"]
        assert ev["completed"]
        verification.append({
            "case_id": row["case_id"], "method": method(row), "completed": ev["completed"],
            **{k: ev[k] for k in ("correct", "total", "wrong", "abstained", "incomplete_claims")},
            "claims": [{k: c[k] for k in ("id", "kind", "verdict", "truth", "correct", "reference_value")}
                       for c in ev["rows"]],
            "scientific_credits": ev["scientific_status"]["spent"],
            "purchases": counts(ev["scientific_status"]), "source_episode": episode_path(row),
        })
    for task, rows, case_key in (("planning", prows, "case_seed"), ("verification", vrows, "case_id")):
        for row in rows:
            if method(row) not in MODELS:
                continue
            relative = episode_path(row)
            tools = read(relative + "/tools.json")
            if task in schemas and schemas[task] != tools:
                raise ValueError("tool schemas differ within a task")
            schemas[task] = tools
            prompts.append({"task": task, "case_id": str(row[case_key]),
                            "method": method(row), "messages": read(relative + "/prompts.json")})
    plan_manifest = read(PLAN + "/manifest.json")
    cases = {"schema_version": 1, "scope": "published development cases; NOT a hidden test set",
             "planning": planning_cases, "verification": catalog["cases"]}
    outcomes = {"schema_version": 1, "planning": planning, "verification": verification,
                "model_reasoning": "high", "verification_luna": {
                    "view": retry["label"],
                    "attempts": retry["total_live_attempts_including_original"],
                    "first_attempt_completed": retry["original_first_attempt_completion"],
                    "first_attempt_counts": {"correct": 8, "wrong": 5, "abstained": 2, "unsubmitted": 3},
                }}
    write("examples/predator_prey/cases.json", cases)
    write("results/predator_prey/results.json", outcomes)
    write("results/predator_prey/prompts.json", prompts)
    write("results/predator_prey/tools.json", schemas)
    write("results/predator_prey/provenance.json", {
        "schema_version": 1,
        "export_source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip(),
        "recorded_numerical_versions": plan_manifest["versions"],
        "baseline_settings": plan_manifest["settings"],
        "config": plan_manifest["config"],
        "source_archive_sha256": sources, "bundle_sha256": dict(exports),
        "note": "Archive paths are provenance identifiers, not distributed dependencies. "
                "Prompts are API-visible task inputs, not raw internal reasoning. "
                "Raw provider responses and credentials are excluded.",
    })
    print("Exported five reviewed JSON files; no model calls.")


if __name__ == "__main__":
    main()
