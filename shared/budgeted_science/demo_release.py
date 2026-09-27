"""Portable, offline access to the two published predator-prey pilots.

results: summarize recorded outcomes (no solvers). cpu: rerun only the shared
numerical baseline. No command enables model/API execution or reads credentials.
Historical runners and frozen preparations remain unchanged.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics

ROOT = Path(__file__).resolve().parents[2]
METHODS = ("adaptive_multifidelity_design", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna")
LABELS = ("Adaptive multifidelity baseline", "GPT-5.6 Sol", "GPT-5.6 Terra", "GPT-5.6 Luna")


def load_bundle(root=ROOT):
    root = Path(root)
    provenance = json.loads((root / "results/predator_prey/provenance.json").read_text(encoding="utf-8"))
    for relative, expected in provenance["bundle_sha256"].items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("bundle path escapes repository")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("bundle hash mismatch: " + relative)
    cases = json.loads((root / "examples/predator_prey/cases.json").read_text(encoding="utf-8"))
    results = json.loads((root / "results/predator_prey/results.json").read_text(encoding="utf-8"))
    for task, ids in (("planning", {str(c["case_seed"]) for c in cases["planning"]}),
                      ("verification", {c["case_id"] for c in cases["verification"]})):
        expected = {(m, i) for m in METHODS for i in ids}
        actual = [(r["method"], r["case_id"]) for r in results[task]]
        if len(actual) != len(expected) or set(actual) != expected:
            raise ValueError("missing or duplicate result rows: " + task)
    return cases, results, provenance


def summarize(results):
    output = []
    for method in METHODS:
        plan = [r for r in results["planning"] if r["method"] == method]
        verify = [r for r in results["verification"] if r["method"] == method]
        errors = [r["max_relative_error"] for r in plan if r["completed"]]
        output.append({
            "method": method, "planning_cases": len(plan),
            "successes": sum(r["success"] for r in plan),
            "mean_max_error": statistics.mean(errors) if errors else None,
            "median_max_error": statistics.median(errors) if errors else None,
            "correct": sum(r["correct"] for r in verify),
            "total_claims": sum(r["total"] for r in verify),
            "wrong": sum(r["wrong"] for r in verify),
            "abstained": sum(r["abstained"] for r in verify),
        })
    return output


def truth_counts(results):
    claims = [c for r in results["verification"] if r["method"] == METHODS[0] for c in r["claims"]]
    return {kind: dict(Counter(c["truth"] for c in claims if c["kind"] == kind))
            for kind in sorted({c["kind"] for c in claims})}


def print_results(results):
    print("| Method | Planning pass | Mean max. error | Median max. error | Verification correct | Wrong | Abstain |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for label, row in zip(LABELS, summarize(results)):
        print(f"| {label} | {row['successes']}/{row['planning_cases']} | "
              f"{row['mean_max_error']*100:.2f}% | {row['median_max_error']*100:.2f}% | "
              f"{row['correct']}/{row['total_claims']} | {row['wrong']} | {row['abstained']} |")
    print("\nClaim balance (truth labels):", json.dumps(truth_counts(results), sort_keys=True))
    print("Recorded model runs, high reasoning; no new API calls. Luna verification includes one retry (7 attempts).")


def cpu(task="both", output=None):
    # Lazy imports: the results command needs only the standard library.
    import numpy as np
    import scipy
    from .agents.records import RunLog
    from .resource_planning import adaptive_design_pilot as planning
    from .paired_claim_audit import adaptive_target_three_pilot as verification
    cases, saved, provenance = load_bundle()
    run = RunLog(output or ROOT / "tmp/released_pilots", "cpu-" + task)
    results = []
    run.write_json("manifest.json", {
        "kind": "CPU reproduction, not new agent evidence", "task": task,
        "python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
        "bundle_sha256": provenance["bundle_sha256"], "api_expenditure_usd": 0,
        "code_sha256": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in sorted((ROOT / "shared/budgeted_science").rglob("*.py"))},
    })
    try:
        if task in ("planning", "both"):
            for case in cases["planning"]:
                # No archived comparisons are loaded by run_case.
                paired = [{"method": METHODS[1], "case_seed": case["case_seed"],
                           "evaluation": {"scientific_status": {
                               "observations": case["initial_observations"]}}}]
                row = planning.run_case(case["case_seed"], run.path / "planning", paired)
                ev = row["evaluation"]
                expected = next(r for r in saved["planning"] if r["method"] == METHODS[0]
                                and r["case_id"] == str(case["case_seed"]))
                valid = bool(ev and ev["valid"])
                measured = ev["parameter_error"]*.05 if valid else None
                match = (valid and ev["theta_true"] == case["theta_true"] and row["accounting_valid"]
                         and ev["success"] == expected["success"]
                         and math.isclose(measured, expected["max_relative_error"], rel_tol=1e-5, abs_tol=1e-7)
                         and row["resource_counts"] == expected["purchases"]
                         and row["scientific_status"]["spent"] == expected["scientific_credits"])
                results.append({"task": "planning", "case_id": str(case["case_seed"]),
                                "matches_recorded": bool(match), "max_relative_error": measured,
                                "result": row})
                run.event("case_finished", **results[-1])
                print("planning", case["case_seed"], "matches_recorded=", bool(match), flush=True)
        if task in ("verification", "both"):
            for case in cases["verification"]:
                # Public and private fields are separated by the existing Episode.
                row = verification.run_case(case, run.path / "verification")
                ev = row["evaluation"]
                expected = next(r for r in saved["verification"] if r["method"] == METHODS[0]
                                and r["case_id"] == case["case_id"])
                observed = {c["id"]: (c["verdict"], c["truth"]) for c in ev["rows"]}
                reference = {c["id"]: (c["verdict"], c["truth"]) for c in expected["claims"]}
                match = (ev["completed"] and row["accounting_valid"] and observed == reference
                         and row["resource_counts"] == expected["purchases"]
                         and ev["scientific_status"]["spent"] == expected["scientific_credits"])
                results.append({"task": "verification", "case_id": case["case_id"],
                                "matches_recorded": bool(match), "result": row})
                run.event("case_finished", **results[-1])
                print("verification", case["case_id"], "matches_recorded=", bool(match), flush=True)
        summary = {"results": results, "all_match": all(r["matches_recorded"] for r in results),
                   "api_expenditure_usd": 0}
        run.write_json("summary.json", summary)
        run.event("finished", all_match=summary["all_match"])
    finally:
        run.close()
    print("New local CPU logs:", run.path)
    if not summary["all_match"]:
        print("Results differ from the archive; inspect logs and numerical versions. No retries were performed.")
    return 0 if summary["all_match"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    commands.add_parser("results")
    run = commands.add_parser("cpu")
    run.add_argument("--task", choices=("both", "planning", "verification"), default="both")
    run.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.mode == "results":
        _, results, _ = load_bundle()
        print_results(results)
        return 0
    return cpu(args.task, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
