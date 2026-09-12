"""Ten development studies; frozen CPU controls at three RHS-work budgets.

No API, model integration, or credentials. Selection uses numerical consequence,
never policy outcomes. Preserve negative findings rather than retuning a winner.
"""

import argparse
from copy import deepcopy
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
from time import perf_counter

import numpy as np
from scipy.optimize import lsq_linear

from ..agents.records import RunLog, digest, json_text, read_events
from . import VERSION, numerics as num
from .environment import Episode

ROOT = Path(__file__).resolve().parents[3]
RUNS = ROOT/"demos/claim_verification/runs"
TARGETS = ((.9, .065, 1.2), (1.2, .10, 1.6))
BUDGETS = (4, 8, 16)
POLICIES = ("prediction_only", "fit_focused", "fixed_split", "adaptive_residual", "full_recompute", "integral_match")
TOLERANCE = .03


def provenance():
    files = list(Path(__file__).parent.glob("*.py"))
    files += [Path(num.rhs.__code__.co_filename), Path(__file__).parents[1]/"agents/records.py"]
    return {"sources": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
            "software": {"python": platform.python_version(), "numpy": version("numpy"), "scipy": version("scipy")}}


def build_catalog(log=None):
    studies, commissioning = [], []
    for system_index, target in enumerate(TARGETS):
        ref = num.reference(target)
        cache = {}
        def calculate(p, experiment, method):
            key = digest([list(p), experiment, method])
            if key not in cache:
                cache[key] = num.solve(p, experiment, method)
            return deepcopy(cache[key])
        p = (num.BOUNDS[:, 0]+np.array([.25,.75,.25])*num.SCALE).tolist()
        fits = []
        for i in range(8):
            calibration = calculate(p, "calibration", "dop_tight")
            rmse = float(np.sqrt(np.mean(num.residual(calibration["values"], ref["data"])**2)))
            fits.append({"theta": list(p), "rmse": rmse, "iterations": i, "calibration": calibration})
            step = num.fit_step(p, ref["data"], lambda pp: calculate(pp, "calibration", "dop_tight"))
            if step["best"] is None:
                raise ValueError("generation fit failed")
            p = step["best"]["theta"]
        perfect = {"theta": ref["fitted_theta"], "rmse": ref["checks"]["recovered"][0]["normalized_rmse"],
                   "iterations": None, "calibration": calculate(ref["fitted_theta"], "calibration", "dop_tight")}
        rows = []
        for fit_index, fit in enumerate([perfect]+fits):
            for method in ("dop_tight", "rk2_0.1", "rk2_0.2", "rk2_0.4", "rk2_0.8"):
                prediction = calculate(fit["theta"], "prediction", method)
                value = float(format(prediction["q"], ".10g")) if prediction["status"] == "complete" else None
                row = {"system": system_index, "fit_index": fit_index, "method": method,
                       "status": prediction["status"], "value": value,
                       "error": abs(value-ref["q"])/abs(ref["q"]) if value is not None else None}
                commissioning.append(row)
                if value is not None:
                    rows.append((row, fit, prediction))
        for family in ("sound", "fit", "prediction", "both", "harmless_combination"):
            def eligible(item):
                row = item[0]
                if family == "sound":
                    return row["fit_index"] == 0 and row["method"] == "dop_tight" and row["error"] < .001
                if family == "fit":
                    return row["fit_index"] > 0 and row["method"] == "dop_tight" and row["error"] >= .036
                if family == "prediction":
                    return row["fit_index"] == 0 and row["method"] != "dop_tight" and row["error"] >= .036
                if family == "both":
                    fit_q = calculate(item[1]["theta"], "prediction", "dop_tight")["q"]
                    fit_error = abs(fit_q-ref["q"])/abs(ref["q"])
                    numerical_effect = abs(item[2]["q"]-fit_q)/abs(fit_q)
                    return row["fit_index"] > 0 and row["method"] != "dop_tight" and row["error"] >= .036 and fit_error >= .036 and numerical_effect >= .01
                return row["fit_index"] > 0 and row["method"] != "dop_tight" and .001 <= row["error"] <= .024
            allowed = [r for r in rows if eligible(r)]
            if not allowed:
                if log:
                    log.write_json("commissioning-failed.json", commissioning)
                raise ValueError(f"unfilled category {system_index}/{family}; no silent substitution")
            desired = .015 if family == "harmless_combination" else .08 if family != "sound" else 0
            row, fit, prediction = min(allowed, key=lambda v: (abs(v[0]["error"]-desired), v[0]["fit_index"], v[0]["method"]))
            fit_record = {"theta": list(fit["theta"]), "rmse": fit["rmse"], "result_id": "original-calibration",
                          "method": "dop_tight", "iterations_recorded": fit["iterations"]}
            claim = {"quantity": "forecast prey at t=24", "value": row["value"], "tolerance": TOLERANCE}
            public = {"report": f"Fitting the supplied calibration data and forecasting from (20,2) gives x(24)={row['value']:.10g}, claimed accurate within 3% relative error.",
                "claim": claim, "data": ref["data"], "calibration_times": num.CAL_TIMES.tolist(),
                "calibration_initial": num.CAL_INITIAL, "prediction_initial": num.PRED_INITIAL,
                "prediction_horizon": 24., "bounds": num.BOUNDS.tolist(),
                "equations": ["x'=theta1*x-theta2*x*y-0.01*x*x", "y'=0.9*theta2*x*y-theta3*y"],
                "reference_contract": "Fully converged bounded least-squares fit to this fixed noiseless dataset, followed by a converged forecast. No new target observations or physical validation.",
                "residual_normalization": list(num.CAL_INITIAL), "methods": num.METHODS,
                "work_proxy": "1 credit = 256 evaluated two-component RHS calls, including all fitting predictors and failed/interrupted work. Analysis and stored-record reuse are free."}
            studies.append({"id": "study-"+digest([VERSION, system_index, family])[:14],
                "public": public, "fit": fit_record, "calibration": fit["calibration"], "prediction": prediction,
                "reference": ref, "private": {"system_index": system_index, "family": family,
                    "selection": row, "cohort": "development", "target": list(target)}})
        if log:
            log.write_json(f"commissioning/system-{system_index}.json", {"reference": ref, "fits": fits,
                "sweep": [r for r in commissioning if r["system"] == system_index]})
    permutation = np.random.default_rng(20260913).permutation(len(studies))
    return [studies[int(i)] for i in permutation], commissioning


def integral_estimate(public):
    """No forward solves: trapezoidal integral identities linear in parameters.

    Discretization error remains. This legal data-only shortcut is a control,
    not the reference fitter and not a guaranteed accurate inverse solution.
    """
    times = np.r_[0., public["calibration_times"]]
    values = np.vstack([public["calibration_initial"], public["data"]])
    integrals = np.cumsum(np.diff(times)[:, None]*(values[:-1]+values[1:])/2, axis=0)
    a, b = [], []
    for t, (x, y), (ix, iy) in zip(times[1:], values[1:], integrals):
        a.extend(([t, -iy, 0.], [0., .9*ix, -t]))
        b.extend((np.log(x/values[0, 0])+.01*ix, np.log(y/values[0, 1])))
    a, b = np.asarray(a), np.asarray(b)
    fit = lsq_linear(a*num.SCALE, b-a@num.BOUNDS[:, 0], bounds=(0., 1.), tol=1e-12)
    return (num.BOUNDS[:, 0]+fit.x*num.SCALE).tolist()


def policy(tools, name):
    if name not in POLICIES:
        raise ValueError("unknown policy")
    initial = tools.call("describe")
    public, best = initial["study"], initial["prediction"]
    total = initial["budget"]["work_remaining"]
    fit_id, fitting = "original-fit", initial["fit"]
    prediction_method = "dop_loose"
    if name == "integral_match":
        prepared = tools.call("register_fit", {"theta": integral_estimate(public)})
        fit_id = prepared["fit_id"]
    elif name == "prediction_only":
        prediction_method = "dop_tight"
    elif name in ("fit_focused", "fixed_split", "full_recompute"):
        allowance = max(0, total-256) if name == "fit_focused" else total//2 if name == "fixed_split" else max(0, total-512)
        # The full-workflow control uses efficient adaptive integration, not an
        # artificially expensive tight solver that handicaps ordinary recompute.
        fitting_method = "dop_tight" if name == "fit_focused" else "dop_loose"
        updated = tools.call("fit_full", {"fit_id": fit_id, "method": fitting_method, "max_work": allowance})
        if "fit_id" in updated:
            fit_id = updated["fit_id"]
        if name == "fit_focused":
            prediction_method = "rk2_0.2"
    else:
        # Residual is a heuristic diagnostic, NOT an error bound for the forecast.
        # Reserve up to two credits for a loose adaptive forecast; inspect each
        # completed fit update before deciding whether another is worthwhile.
        for _ in range(8):
            remaining = tools.call("budget")["budget"]["work_remaining"]
            if (fitting["rmse"] is not None and fitting["rmse"] <= .01) or remaining <= 512:
                break
            updated = tools.call("fit_step", {"fit_id": fit_id, "method": "dop_loose", "max_work": remaining-512})
            if "fit_id" not in updated:
                break
            new = updated["fit"]
            prior = fitting["rmse"]
            fit_id, fitting = updated["fit_id"], new
            if updated["status"] != "complete" or new["rmse"] is None or (prior is not None and new["rmse"] >= prior*.999):
                break
    remaining = tools.call("budget")["budget"]["work_remaining"]
    check = tools.call("predict", {"fit_id": fit_id, "method": prediction_method, "max_work": remaining})
    if check.get("status") == "complete":
        best = check
    else:
        # No substitution of an unevaluated forecast at newly fitted parameters.
        return tools.call("submit", {"verdict": "ABSTAIN", "evidence_ids": [fit_id],
            "justification": "No completed forecast using the chosen fit; original retained but not treated as a repaired result."})
    if name == "adaptive_residual":
        difference = abs(public["claim"]["value"]-best["q"])/abs(best["q"])
        remaining = tools.call("budget")["budget"]["work_remaining"]
        if .015 < difference < .06 and remaining >= 256:
            refined = tools.call("predict", {"fit_id": fit_id, "method": "dop_tight", "max_work": remaining})
            if refined.get("status") == "complete":
                best = refined
    difference = abs(public["claim"]["value"]-best["q"])/abs(best["q"])
    verdict = "ACCEPT" if difference <= public["claim"]["tolerance"]+1e-12 else "REJECT"
    return tools.call("submit", {"verdict": verdict, "evidence_ids": [fit_id, best["result_id"]],
        "justification": f"{name}: original {public['claim']['value']} versus computed {best['q']}; relative difference {difference}. Not a certified error bound."})


def render(path):
    path = Path(path)
    manifest = json.loads((path/"manifest.json").read_text(encoding="utf-8"))
    rows = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((path/"episodes").glob("*/result.json"))]
    slots = [(r["case_id"], r["budget"], r["policy"]) for r in rows]
    allowed = {(c["id"], b, p) for c in manifest["cases"] for b in manifest["budgets"] for p in manifest["policies"]}
    if len(set(slots)) != len(slots) or not set(slots).issubset(allowed):
        raise ValueError("duplicate or unexpected episode slot")
    summary = {"studies": len(manifest["cases"]), "systems": len(manifest["targets"]), "episodes": len(rows), "api_usd": 0,
               "missing_slots": len(allowed-set(slots)),
               "by_budget": {}}
    for budget in manifest["budgets"]:
        summary["by_budget"][str(budget)] = {}
        for name in manifest["policies"]:
            group = [r for r in rows if r["policy"] == name and r["budget"] == budget]
            summary["by_budget"][str(budget)][name] = {"correct": sum(r["evaluation"]["correct"] for r in group),
                "count": len(group), "abstained": sum(r["evaluation"]["abstained"] for r in group),
                "incomplete": sum(r["evaluation"]["incomplete"] for r in group),
                "false_accept": sum(r["evaluation"]["verdict"] == "ACCEPT" and not r["evaluation"]["valid"] for r in group),
                "false_reject": sum(r["evaluation"]["verdict"] == "REJECT" and r["evaluation"]["valid"] for r in group),
                "mean_seconds": float(np.mean([r["seconds"] for r in group])) if group else None,
                "mean_credits": float(np.mean([r["evaluation"]["spent"] for r in group])) if group else None}
    lines = ["# Fitting/prediction verification CPU pilot", "", "Ten development studies from two systems. No API calls or confidence/diagnosis grading.",
        "```json", json_text(summary), "```", "", "| Case | Family | Budget | Policy | Verdict | Correct | Credits | Trace |",
        "|---|---|---:|---|---|---|---:|---|"]
    for r in rows:
        e = r["evaluation"]
        lines.append(f"| {r['case_id']} | {r['family']} | {r['budget']} | {r['policy']} | {e['verdict']} | {e['correct']} | {e['spent']:.4f} | [Events]({r['path']}/events.jsonl) |")
        episode_path = path/r["path"]
        events, torn = read_events(episode_path)
        transcript = ["# Scripted CPU policy trace", "", f"Policy: {r['policy']}. No language model or API calls.", ""]
        for event in events:
            if event["kind"] in ("tool_request", "tool_result", "failure", "unaccounted_failure"):
                transcript.extend([f"## {event['sequence']}: {event['kind']}", "", "```json", json_text(event), "```", ""])
        if torn:
            transcript.append("The final event line was interrupted; complete earlier events are preserved.")
        (episode_path/"transcript.md").write_text("\n".join(transcript)+"\n", encoding="utf-8")
    (path/"summary.json").write_text(json_text(summary)+"\n", encoding="utf-8")
    (path/"report.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    return summary


def run(output_root=RUNS):
    log = RunLog(output_root, "fit-prediction-cpu")
    print(log.path, flush=True)
    try:
        frozen = provenance()
        studies, commissioning = build_catalog(log)
        log.write_json("catalog.json", studies)
        log.write_json("commissioning.json", commissioning)
        manifest = {"version": VERSION, "budgets": BUDGETS, "policies": POLICIES, "targets": TARGETS,
            "cases": [{"id": s["id"], "hash": digest(s)} for s in studies], "catalog_hash": digest(studies),
            "frozen_before_policy_results": True, **frozen}
        log.write_json("manifest.json", manifest)
        log.event("campaign_started", cases=len(studies), budgets=BUDGETS)
        for budget in BUDGETS:
            for s in studies:
                for name in POLICIES:
                    if provenance() != frozen:
                        raise RuntimeError("source changed during frozen experiment")
                    child = RunLog(log.path/"episodes", name)
                    start = perf_counter()
                    episode = Episode(s, budget, child)
                    child.write_json("public.json", {"study": s["public"], "fit": s["fit"]})
                    child.write_json("originals.json", {"calibration": s["calibration"], "prediction": s["prediction"]})
                    failure = None
                    try:
                        policy(episode.tools, name)
                    except Exception as exc:
                        failure = f"{type(exc).__name__}: {exc}"
                        episode.state = "aborted"
                        child.event("failure", error=failure)
                    row = {"case_id": s["id"], "family": s["private"]["family"], "budget": budget, "policy": name,
                           "evaluation": episode.evaluation(), "submission": episode.submission, "failure": failure,
                           "seconds": perf_counter()-start, "path": str(child.path.relative_to(log.path))}
                    child.write_json("result.json", row)
                    child.event("episode_finished", result=row)
                    child.close()
                    log.event("episode_completed", result=row)
                print(budget, s["id"], s["private"]["family"], flush=True)
        log.event("campaign_finished", episodes=len(studies)*len(BUDGETS)*len(POLICIES))
        summary = render(log.path)
        print(json_text(summary), flush=True)
    finally:
        log.close()
    return log.path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("cpu", "render"))
    parser.add_argument("--path", type=Path)
    parser.add_argument("--output-root", type=Path, default=RUNS)
    args = parser.parse_args()
    if args.action == "render":
        if args.path is None:
            parser.error("render requires --path")
        print(json_text(render(args.path)))
    else:
        run(args.output_root)


if __name__ == "__main__":
    main()
