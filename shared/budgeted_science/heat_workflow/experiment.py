"""Four development studies and two CPU controls; no agent/API integration."""

import argparse
from dataclasses import asdict, replace
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
from time import perf_counter

import numpy as np

from ..agents.records import RunLog, digest, read_events, utc_now
from . import VERSION
from .numerics import (PATCH, TOLERANCE, Config, Problem, analysis_source,
                       analyze_owned_source, classify, patch_mean, solve_direct,
                       solve_jacobi, validate)

ROOT = Path(__file__).resolve().parents[3]
RUNS = ROOT / "demos" / "claim_verification" / "runs"


def study_specs():
    """Predeclared development fixtures, not severity- or policy-selected cases."""
    return [
        ("sound", Problem(), Config(), False),
        ("premature_stopping", Problem(), Config(relaxation=0.02, update_tolerance=2e-4), False),
        ("spatial_extraction", Problem(), Config(), True),
        ("boundary_mismatch", Problem(left=0.5), Config(), False),
    ]


def public_specification():
    return {"equation": "T_xx + T_yy = 0", "domain": [0, 1, 0, 1],
            "boundaries": asdict(Problem()), "temperature": "dimensionless",
            "quantity": "area-mean steady temperature over the specified rectangle",
            "patch": {"x": list(PATCH[:2]), "y": list(PATCH[2:])}, "relative_tolerance": TOLERANCE,
            "array_convention": "T[i,j] is the temperature at (x[i],y[j])"}


def provenance():
    files = list(Path(__file__).parent.glob("*.py"))
    files += [ROOT / "shared/budgeted_science/agents/records.py", ROOT / "tests/test_heat_workflow.py"]
    return {"version": VERSION, "python": platform.python_version(), "platform": platform.platform(),
            "dependencies": {p: importlib.metadata.version(p) for p in ("numpy", "scipy")},
            "source_sha256": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in sorted(files) if p.exists()}}


def save_field(log, relative, field):
    path = log.path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    grid = np.linspace(0, 1, len(field))
    with path.open("xb") as stream:
        np.savez_compressed(stream, x=grid, y=grid, T=field)
    return relative


def write_text(log, relative, text):
    path = log.path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(text)


def control(study, method, record=None):
    """Only public study information; neither reference nor development labels enter."""
    start = perf_counter()
    calls = []

    def retain(field, info, value):
        calls.append({**info, "analyzed_Q": value})
        if record is not None:
            record(field, calls[-1], len(calls))

    if method == "refinement_only":
        cfg = replace(Config(**study["run_config"]["numerical"]), n=65,
                      relaxation=0.8, update_tolerance=1e-12, max_iterations=50000)
        executed_problem = Problem(**study["run_config"]["boundaries"])
        field, info = solve_jacobi(executed_problem, cfg)
        value = analyze_owned_source(study["analysis_source"], field)
        retain(field, info, value)
        if info["status"] != "update_threshold_reached":
            return {"method": method, "status": "incomplete", "verdict": None,
                    "calls": calls, "seconds": perf_counter()-start}
    elif method == "independent_reconstruction":
        intended = Problem(**study["intended"]["boundaries"])
        values = []
        for n in (33, 65):
            field, info = solve_direct(intended, n)
            region = study["intended"]["patch"]
            value = patch_mean(field, (*region["x"], *region["y"]))
            values.append(value)
            retain(field, info, value)
        # This is a practical mesh-agreement check, not a certified error bound.
        if abs(values[-1]-values[-2]) / abs(values[-1]) > 0.01:
            return {"method": method, "status": "completed", "verdict": "ABSTAIN",
                    "calls": calls, "seconds": perf_counter()-start}
    else:
        raise ValueError("unknown CPU control")
    return {"method": method, "status": "completed", "estimate": value,
            **classify(study["reported_Q"], value, study["intended"]["relative_tolerance"]),
            "calls": calls, "seconds": perf_counter()-start}


def file_hashes(directory):
    return {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob("*")) if p.is_file()
            and p.relative_to(directory).as_posix() not in ("report.md", "completion.json")}


def render(directory):
    """Read saved artifacts only; no simulation, analysis execution, or API calls."""
    directory = Path(directory)
    completion = json.loads((directory / "completion.json").read_text(encoding="utf-8"))
    if file_hashes(directory) != completion["artifact_sha256"]:
        raise ValueError("artifact hash mismatch; refusing to render changed evidence")
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    events, torn = read_events(directory)
    if torn or not events or events[-1]["kind"] != "finished":
        raise ValueError("incomplete event archive")
    lines = ["# Heat-plate workflow audit: CPU prototype", "",
             f"Run status: {summary['status']}. API expenditure: $0. No LLM calls.", "",
             "Four deliberately authored development studies share ONE physical target. "
             "Two controls give eight executions, not eight independent systems. "
             "No scientific-credit cap, cost reward, or validated uncertainty score is used.", "",
             "The implementation uses the same kind of five-point discretization as SimulCost's "
             "steady heat example. It does not execute or vendor the SimulCost package.", "",
             "## Study outcomes", "",
             "Truth is the literal reported quantity within 5% of an independently checked "
             "continuous harmonic-series reference. A suspicious setting is not itself a false claim.", "",
             "| Study | Development construction | Reported Q | True error | Truth | Original iterations |",
             "|---|---|---:|---:|---|---:|"]
    for case in summary["cases"]:
        lines.append(f"| [{case['id']}](studies/{case['id']}/public/report.md) | {case['category']} | "
                     f"{case['reported_Q']:.10g} | {100*case['truth']['relative_error']:.5f}% | "
                     f"{case['truth']['verdict']} | {case['original']['iterations']} |")
    lines += ["", "## CPU controls", "",
              "Refinement-only changes numerical resolution/convergence, preserving actual boundary "
              "inputs and the original analysis. Independent reconstruction instead uses the stated "
              "problem, separate sparse matrix assembly, and the stated patch; it ignores the study's "
              "analysis script. Neither control receives the private series reference or labels.", "",
              "| Study | Control | Verdict | Correct | CPU + artifact time (s) | Trace |",
              "|---|---|---|---|---:|---|"]
    for row in summary["results"]:
        lines.append(f"| {row['study_id']} | {row['method']} | {row.get('verdict')} | "
                     f"{row['correct']} | {row['seconds']:.4f} | [{row['status']}]({row['artifact']}) |")
    for method in ("refinement_only", "independent_reconstruction"):
        rows = [r for r in summary["results"] if r["method"] == method]
        lines += ["", f"{method}: {sum(r['correct'] for r in rows)}/{len(summary['cases'])} correct; "
                  f"{sum(r['status'] != 'completed' for r in rows)} incomplete."]
    lines += ["", "## Numerical checks", "",
              f"Reference mean: {summary['validation'].get('reference')}; "
              f"128/256-series agreement: {summary['validation'].get('fourier_128_256_difference')}.", "",
              "| Grid | Direct mean | Error vs continuous reference | Direct solver seconds |",
              "|---:|---:|---:|---:|"]
    for row in summary["validation"].get("grid_study", []):
        lines.append(f"| {row['n']} | {row['value']:.10f} | {100*row['relative_error']:.6f}% | {row['seconds']:.4f} |")
    lines += ["", "## Interpretation and accounting", "",
              "The stronger control remains available and cheap; no budgeted-investigation challenge "
              "or advantage for an agent has been established. These are smoke-test errors, not a "
              "sample of natural scientific mistakes. All cases use the same report template. "
              "Explanations and diagnoses are not automatically graded.", "",
              "Jacobi records grid points times performed iterations (a work proxy, not FLOPs). "
              "Sparse solves record unknowns, matrix nonzeros, and runtime; those counts are NOT "
              "equivalent costs. Control elapsed times include numerical-artifact writing; individual "
              "solver timings exclude it. Python startup and evaluator construction are excluded. "
              "No results are backend-cached between controls.", "",
              "References are a converged series checked against mesh refinement, not mathematically "
              "certified intervals. Series coefficients and the evaluator stay outside public study "
              "folders. This is file organization, not a sandbox. Only two exact repository-owned "
              "analysis templates may execute; arbitrary agent code is outside this prototype.", "",
              "[Numerical validation](private/validation.json) · [Frozen manifest](manifest.json) · "
              "[Complete events](events.jsonl) · [Machine-readable results](summary.json)", ""]
    (directory / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return directory / "report.md"


def run(root=RUNS):
    log = RunLog(root, "heat-workflow-cpu")
    summary = {"status": "incomplete", "cases": [], "results": [], "validation": {}, "api_dollars": 0}
    log.write_json("manifest.json", {**provenance(), "started": utc_now(),
                   "public_problem": public_specification(), "budget": None,
                   "private_development_constructions": [
                       {"category": label, "boundaries": asdict(p), "numerical": asdict(c), "transpose": t}
                       for label, p, c, t in study_specs()]})
    log.event("started", api_dollars=0)
    try:
        summary["validation"] = validation = validate()
        log.write_json("private/validation.json", validation)
        for index, (label, problem, cfg, transpose) in enumerate(study_specs()):
            case_id = "study-" + digest({"version": VERSION, "slot": index})[:10]
            public = f"studies/{case_id}/public"
            log.event("study_started", study_id=case_id)
            source = analysis_source(transpose)
            field, info = solve_jacobi(problem, cfg)
            if info["status"] != "update_threshold_reached":
                raise ArithmeticError(f"study construction incomplete: {case_id}: {info['status']}")
            computed = analyze_owned_source(source, field)
            reported = float(f"{computed:.10g}")
            study = {"intended": public_specification(), "reported_Q": reported,
                     "run_config": {"boundaries": asdict(problem), "numerical": asdict(cfg)},
                     "analysis_source": source}
            save_field(log, f"{public}/trajectory.npz", field)
            log.write_json(f"{public}/intended.json", study["intended"])
            log.write_json(f"{public}/run_config.json", study["run_config"])
            log.write_json(f"{public}/solver_log.json", info)
            log.write_json(f"{public}/analysis_result.json", {"computed_Q": computed, "reported_Q": reported})
            write_text(log, f"{public}/analysis.py", source)
            write_text(log, f"{public}/report.md", "# Steady heat study\n\n"
                       "The intended problem and coordinate convention are in `intended.json`.\n\n"
                       f"We report a mean dimensionless temperature of **{reported:.10g}** over "
                       "x=[0.1,0.3], y=[0.6,0.8], accurate within **5%** of the steady-state value.\n\n"
                       "The executed configuration, solver log, raw field, and analysis script are supplied.\n")
            truth = classify(reported, validation["reference"])
            case = {"id": case_id, "category": label, "reported_Q": reported,
                    "truth": truth, "original": info}
            summary["cases"].append(case)
            log.write_json(f"private/{case_id}.json", case)
            log.event("study_created", study_id=case_id, reported_Q=reported, original=info)
            for method in ("refinement_only", "independent_reconstruction"):
                path = f"controls/{case_id}/{method}"
                log.event("control_started", study_id=case_id, method=method)
                control_start = perf_counter()

                def record(field, info, number):
                    artifact = save_field(log, f"{path}/solve_{number}.npz", field)
                    log.write_json(f"{path}/solve_{number}.json", info)
                    log.event("numerical", study_id=case_id, method=method, artifact=artifact, info=info)

                try:
                    result = control(study, method, record)
                except Exception as exc:
                    result = {"method": method, "status": "incomplete", "verdict": None,
                              "seconds": perf_counter()-control_start, "error": str(exc)}
                    log.event("control_error", study_id=case_id, method=method, error=str(exc))
                result.update(study_id=case_id, artifact=f"{path}/result.json",
                              correct=result.get("verdict") == truth["verdict"])
                log.write_json(result["artifact"], result)
                summary["results"].append(result)
                log.event("control_finished", result=result)
        summary["status"] = "complete"
    except (Exception, KeyboardInterrupt) as exc:
        summary["error"] = str(exc) or type(exc).__name__
        log.event("interrupted", error=summary["error"])
    finally:
        summary["unconstructed_studies"] = 4-len(summary["cases"])
        summary["unattempted_controls"] = 8-len(summary["results"])
        log.write_json("summary.json", summary)
        log.event("finished", status=summary["status"])
        log.close()
    log.write_json("completion.json", {"artifact_sha256": file_hashes(log.path)})
    render(log.path)
    return log.path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "run", "render"))
    parser.add_argument("directory", nargs="?")
    args = parser.parse_args()
    if args.command == "validate":
        print(json.dumps(validate(), indent=2, allow_nan=False))
    elif args.command == "render":
        if not args.directory:
            parser.error("render requires the saved run directory")
        print(render(args.directory))
    else:
        path = run()
        print(path)
        summary = json.loads((path/"summary.json").read_text(encoding="utf-8"))
        if summary["status"] != "complete":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
