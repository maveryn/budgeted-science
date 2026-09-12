"""Twelve development claims and small, fully logged CPU policy comparison.

No API integration. Catalog selection never uses policy outcomes. The hindsight
selector is explicitly a truth-using upper bound over executed checks, NOT an
adaptive baseline or a measure of an agent's attainable performance.
"""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import platform
import time
from uuid import uuid4

import numpy as np
import scipy

from budgeted_science.agents.records import RunLog, digest, json_text, read_events
from . import VERSION
from . import numerics as num
from .environment import Backend, Episode, relative_error, within

ROOT = Path(__file__).resolve().parents[3]
RUNS = ROOT/"demos"/"claim_verification"/"runs"
BUDGET = 4.
TOLERANCE = 0.03
POLICIES = ("balanced", "space_focused", "time_focused", "output_focused", "random")


def sources():
    paths = sorted(Path(__file__).parent.glob("*.py")) + [Path(__file__).parents[1]/"agents"/"records.py"]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def original_configs():
    return [
        num.config(32, 1/128, "upwind", "RK2", 1/32),
        num.config(64, 1/256, "upwind", "RK2", 1/128),
        num.config(32, 1/128, "centered", "RK2", 1/128),
        num.config(64, 1/256, "centered", "RK2", 1/128),
        num.config(64, 1/256, "centered", "RK2", 1/8),
        num.config(128, 1/1024, "centered", "RK2", 1/256),
        num.config(64, 1/256, "upwind", "Euler", 1/128),
        num.config(32, 1/64, "centered", "RK2", 1/8),
    ]


def public_study(system, cfg, quantity, value, index):
    sentences = (
        "The numerical study reports {q} = {v:.10g}, claimed accurate within 3% relative error.",
        "Notebook conclusion: {q} was {v:.10g}; the claimed relative numerical accuracy is 3%.",
        "Results memo: our estimate of {q} is {v:.10g}, with a claimed relative error no greater than 3%.",
    )
    return {"report": sentences[index % 3].format(q=quantity, v=value),
            "claim": {"quantity": quantity, "value": value, "tolerance": TOLERANCE,
                      "error_type": "relative"},
            "system": deepcopy(system), "equation": "c_t + v*c_x = D*c_xx - k*c",
            "domain": [0., 1.], "boundary": "periodic", "horizon": num.T,
            "initial": {"type": "wrapped Gaussian", "center": num.X0, "width": num.WIDTH},
            "sensor": num.SENSOR, "threshold": num.THRESHOLD, "configuration": cfg,
            "extraction": "Peak and earliest argmax from saved sensor samples; exposure by trapezoids; "
                          "first threshold crossing by linear interpolation between saved samples.",
            "reference_contract": "The equation admits cheap analytic solutions. This prototype only allows "
                                  "the declared numerical tools; it is not a sandbox for arbitrary Python."}


def build_catalog(backend=None, log=None):
    backend = backend or Backend()
    studies, commissioning = [], []
    for system_index, system in enumerate(num.SYSTEMS):
        ref = num.reference(system)
        candidates = []
        for config_index, cfg in enumerate(original_configs()):
            record = {"system_index": system_index, "config_index": config_index, "config": cfg}
            try:
                num.validate(system, cfg)
                run, _ = backend.run(system, cfg)
                qs = num.qois(run)
                if log:
                    record["artifact"] = log.write_json(f"commissioning/system-{system_index}-config-{config_index}.json", run)
                record.update(status="complete", qois=qs,
                              errors={q: relative_error(qs[q], ref["qois"][q]) for q in num.QUANTITIES})
                candidates.append((config_index, run, qs, record["errors"]))
            except ValueError as exc:
                record.update(status="excluded", reason=str(exc))
            commissioning.append(record)
            if log:
                log.event("commissioned_candidate", record=record)
        for qi, quantity in enumerate(num.QUANTITIES):
            desired_valid = (system_index+qi) % 2 == 0
            target_error = .015 if desired_valid else .08
            eligible = [c for c in candidates if c[3][quantity] is not None and
                        (c[3][quantity] <= .024 if desired_valid else c[3][quantity] >= .036)]
            if not eligible:
                raise ValueError(f"commissioning failure: system {system_index}, {quantity}, valid={desired_valid}")
            chosen = min(eligible, key=lambda c: (abs(c[3][quantity]-target_error), c[0]))
            config_index, run, qs, errors = chosen
            value = float(format(qs[quantity], ".10g"))
            study = {"id": "study-"+uuid4().hex[:12], "system": deepcopy(system), "original": deepcopy(run),
                     "reference": ref, "public": public_study(system, run["config"], quantity, value, len(studies)),
                     "private_selection": {"system_index": system_index, "config_index": config_index,
                                           "desired_valid": desired_valid, "target_error": target_error,
                                           "actual_error": errors[quantity], "cohort": "development"}}
            if within(value, ref["qois"][quantity], TOLERANCE) != desired_valid:
                raise ValueError("rounded claim changed commissioning label")
            studies.append(study)
    return studies, commissioning


def configuration_menu(system, budget):
    configs = []
    for nx in (32, 64, 128, 256):
        for nsteps in (64, 128, 256, 512, 1024, 2048, 4096):
            for nout in (8, 16, 32, 64, 128, 256, 512):
                cfg = num.config(nx, 1/nsteps, "centered", "RK2", 1/nout)
                if num.quote(cfg)["credits"] <= budget and num.amplification(system, cfg) <= 1+1e-12:
                    configs.append(cfg)
    return configs


def quality_terms(cfg, public):
    # Public numerical-order heuristic, not a calibrated error bound. Sampled
    # argmax has first-order timing resolution; interpolated crossings use p=2.
    characteristic_time = num.WIDTH/public["system"]["v"]
    p = 1 if public["claim"]["quantity"] == "arrival" else 2
    return np.array([(1/cfg["nx"]/num.WIDTH)**2,
                     (cfg["dt"]/characteristic_time)**2,
                     (cfg["output_dt"]/characteristic_time)**p])


def choose_configuration(public, budget, policy, seed=0):
    if policy not in POLICIES:
        raise ValueError("unknown CPU policy")
    configs = [cfg for cfg in configuration_menu(public["system"], budget)
               if cfg != public["configuration"]]
    if not configs:
        return None
    if policy == "random":
        return configs[int(np.random.default_rng(seed).integers(len(configs)))]
    weights = np.ones(3)
    if policy != "balanced":
        weights[("space_focused", "time_focused", "output_focused").index(policy)] = 16
    return min(configs, key=lambda cfg: (float(quality_terms(cfg, public) @ weights),
                                        num.quote(cfg)["credits"], digest(cfg)))


def run_policy(call, policy, seed=0):
    initial = call("describe")
    public = initial["study"]
    cfg = choose_configuration(public, initial["budget"]["remaining"], policy, seed)
    check = call("run_verification", cfg) if cfg else {"error": "no affordable configuration"}
    value = None if "error" in check or check["status"] != "complete" else check["qois"][public["claim"]["quantity"]]
    evidence = ["original"] + ([check["run_id"]] if "run_id" in check else [])
    claim = public["claim"]
    verdict = "ABSTAIN" if value is None else ("ACCEPT" if within(claim["value"], value, claim["tolerance"]) else "REJECT")
    call("submit", {"verdict": verdict, "evidence_ids": evidence,
                    "justification": "Compare the literal reported value with this fixed-rule purchased check. "
                                     "The check is an approximation, not a certified reference or error bound."})
    return {"estimate": value, "configuration": cfg, "estimated_relative_difference": relative_error(claim["value"], value)}


def render_episode(path):
    path = Path(path)
    events, torn = read_events(path)
    lines = ["# CPU audit transcript", "", "Scripted numerical policy; no model/API calls.", ""]
    for event in events:
        if event["kind"] in ("tool_request", "tool_result"):
            lines.extend([f"## {event['kind']}: {event['name']}", "", "```json",
                          json_text(event.get("arguments", event.get("result"))), "```", ""])
        elif event["kind"] == "numerical_result":
            lines.extend([f"Full numerical artifact: [{event['run_id']}]({event['artifact']})", ""])
    if torn:
        lines.append("Interrupted final event retained; transcript shows complete received events only.")
    (path/"transcript.md").write_text("\n".join(lines), encoding="utf-8")


def episode(study, policy, backend, root):
    log = RunLog(root, "transport-"+policy)
    env = Episode(study, BUDGET, backend, log)
    start, calls, diagnostics = time.perf_counter(), 0, None
    reason = "submitted"
    log.write_json("public.json", study["public"])
    log.write_json("private.json", study)

    def call(name, args=None):
        nonlocal calls
        if calls >= 30 or time.perf_counter()-start > 300:
            raise TimeoutError("CPU episode limit")
        calls += 1
        result = env.tools.call(name, args, f"cpu-{calls}")
        if time.perf_counter()-start > 300:
            raise TimeoutError("CPU episode deadline")
        return result

    try:
        diagnostics = run_policy(call, policy)
    except Exception as exc:
        reason = type(exc).__name__+": "+str(exc)
        env.state = "aborted"
        log.event("interrupted", reason=reason)
    result = {"case_id": study["id"], "policy": policy, "quantity": study["public"]["claim"]["quantity"],
              "evaluation": env.evaluation(), "termination": reason, "diagnostics": diagnostics,
              "runtime_seconds": time.perf_counter()-start, "api_dollars": 0.}
    log.write_json("result.json", result, replace=True)
    log.event("episode_finished", result=result)
    log.close()
    render_episode(log.path)
    return log.path


def aggregate(results, case_ids):
    summary = {"cases": len(case_ids), "episodes": len(results), "policies": {}, "api_dollars": 0.}
    for policy in POLICIES:
        rows = [r for r in results if r["policy"] == policy]
        ev = [r["evaluation"] for r in rows]
        summary["policies"][policy] = {
            "correct": sum(e["correct"] for e in ev), "count": len(case_ids),
            "incomplete": len(case_ids)-len(rows)+sum(e["incomplete"] for e in ev),
            "abstentions": sum(e["abstention"] for e in ev), "coverage": sum(e["coverage"] for e in ev),
            "false_acceptance": sum(e["verdict"] == "ACCEPT" and not e["valid"] for e in ev),
            "false_rejection": sum(e["verdict"] == "REJECT" and e["valid"] for e in ev),
            "mean_spent": float(np.mean([e["spent"] for e in ev])) if ev else None,
            "per_quantity": {q: sum(r["evaluation"]["correct"] for r in rows if r["quantity"] == q) for q in num.QUANTITIES}}
    fixed = POLICIES[:-1]
    best = max(summary["policies"][p]["correct"] for p in fixed)
    oracle = sum(any(r["evaluation"]["correct"] for r in results if r["case_id"] == case and r["policy"] in fixed) for case in case_ids)
    summary.update(best_tested_fixed_correct=best, hindsight_fixed_selection_correct=oracle,
                   hindsight_selection_headroom=oracle-best)
    return summary


def render(path):
    path = Path(path)
    manifest = json.loads((path/"manifest.json").read_text(encoding="utf-8"))
    events, torn = read_events(path)
    results, transcript_links = [], []
    seen = set()
    for event in events:
        if event["kind"] != "episode_completed":
            continue
        child = path/event["path"]
        result = json.loads((child/"result.json").read_text(encoding="utf-8"))
        key = (result["case_id"], result["policy"])
        if key in seen:
            raise ValueError("duplicate case-policy result")
        seen.add(key)
        results.append(result)
        render_episode(child)
        transcript_links.append((result, event["path"]+"/transcript.md"))
    summary = aggregate(results, manifest["case_ids"])
    lines = ["# Transport verification: small CPU development pilot", "",
             "12 claims, three physical systems, five CPU policies. No LLM calls. All cases are development cases.", "",
             "| Policy | Correct / 12 | False accept | False reject | Abstain | Incomplete | Mean credits |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for p, s in summary["policies"].items():
        lines.append(f"| {p} | {s['correct']}/12 | {s['false_acceptance']} | {s['false_rejection']} | {s['abstentions']} | {s['incomplete']} | {s['mean_spent']} |")
    lines.extend(["", f"Best tested fixed rule: {summary['best_tested_fixed_correct']}/12. "
                  f"Hindsight selection among the four executed fixed checks: {summary['hindsight_fixed_selection_correct']}/12. "
                  f"Selection headroom: {summary['hindsight_selection_headroom']} claims.", "",
                  "Hindsight uses private truth and is not a realizable adaptive policy. No statistical or causal adaptivity claim.", "",
                  "## Individual results", "", "| Claim | Quantity | Policy | Verdict | Truth valid | Correct | Credits | Transcript |",
                  "|---|---|---|---|---|---|---:|---|"])
    for r, link in transcript_links:
        e = r["evaluation"]
        lines.append(f"| {r['case_id']} | {r['quantity']} | {r['policy']} | {e['verdict']} | {e['valid']} | {e['correct']} | {e['spent']:.4f} | [log]({link}) |")
    if torn:
        lines.extend(["", "Campaign has an interrupted final log record."])
    (path/"summary.json").write_text(json_text(summary)+"\n", encoding="utf-8")
    (path/"report.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    return summary


def numerical_validation():
    checks = []
    for system in num.SYSTEMS:
        ref = num.reference(system)
        for nx in (32, 64, 128, 256):
            nt = max(256, int(2**np.ceil(np.log2(4*system["D"]*nx*nx+2*system["v"]*nx))))
            cfg = num.config(nx, 1/nt, "centered", "RK2", 1/1024)
            run = num.solve(system, cfg)
            qs = num.qois(run)
            checks.append({"system": system, "config": cfg, "work": run["work"], "credits": run["credits"],
                           "errors": {q: relative_error(qs[q], ref["qois"][q]) for q in num.QUANTITIES},
                           "sensor_max_abs_error": float(np.max(np.abs(np.array(run["sensor"])-num.exact_images(system, num.SENSOR, run["times"])))),
                           "mass_max_abs_error": float(np.max(np.abs(np.array(run["mass"])-num.WIDTH*np.sqrt(2*np.pi)*np.exp(-system["k"]*np.array(run["times"]))))),
                           "reference_checks": ref["checks"]})
    return checks


def axis_diagnostics(studies, backend):
    """Privileged commissioning, not agent evidence or additive defect labels."""
    results = []
    for study in studies:
        original = study["original"]["config"]
        for name, changed in (
            ("mesh", {"nx": original["nx"]*2}),
            ("timestep", {"dt": original["dt"]/2}),
            ("output", {"output_dt": original["output_dt"]/2}),
            ("spatial_method", {"spatial_method": "centered" if original["spatial_method"] == "upwind" else "upwind"}),
        ):
            cfg = {**original, **changed}
            record = {"case_id": study["id"], "axis": name, "configuration": cfg}
            try:
                num.validate(study["system"], cfg)
                result, _ = backend.run(study["system"], cfg)
                qs = num.qois(result)
                q = study["public"]["claim"]["quantity"]
                record.update(status="complete", qoi=qs[q], credits=result["credits"],
                              reference_relative_error=relative_error(qs[q], study["reference"]["qois"][q]),
                              original_relative_change=relative_error(qs[q], study["public"]["claim"]["value"]))
            except ValueError as exc:
                record.update(status="excluded", reason=str(exc))
            results.append(record)
    return results


def run(root=RUNS):
    log = RunLog(root, "transport-cpu")
    frozen = sources()
    log.write_json("protocol.json", {"source_hashes": frozen, "budget": BUDGET, "tolerance": TOLERANCE,
                                     "systems": num.SYSTEMS, "original_configs": original_configs(),
                                     "selection": "alternating truth strata; nearest 1.5% valid / 8% invalid, "
                                                  "with <=2.4% / >=3.6% margins; no policy outcomes used",
                                     "policies": POLICIES, "policy_seed": 0})
    try:
        backend = Backend()
        studies, commissioning = build_catalog(backend, log)
        log.write_json("commissioning.json", commissioning)
        log.write_json("catalog.json", studies)
        log.write_json("numerical_validation.json", numerical_validation())
        log.write_json("axis_diagnostics.json", axis_diagnostics(studies, backend))
        fixed = {s["id"]: {p: choose_configuration(s["public"], BUDGET, p) for p in POLICIES} for s in studies}
        log.write_json("manifest.json", {"version": VERSION, "case_ids": [s["id"] for s in studies],
                                        "catalog_hash": digest(studies), "source_hashes": frozen,
                                        "software": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
                                        "frozen_configurations": fixed, "budget": BUDGET, "api_dollars": 0.})
        # All original cases and policy configurations are frozen before any verdict is evaluated.
        for study in studies:
            for policy in POLICIES:
                if sources() != frozen:
                    raise RuntimeError("source changed after protocol freeze")
                child = episode(study, policy, backend, log.path/"episodes")
                log.event("episode_completed", case_id=study["id"], policy=policy, path=child.relative_to(log.path).as_posix())
        log.event("campaign_finished")
    except BaseException as exc:
        log.event("campaign_interrupted", exception=type(exc).__name__, message=str(exc))
        raise
    finally:
        log.close()
    summary = render(log.path)
    return log.path, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    execute = sub.add_parser("run")
    execute.add_argument("--root", type=Path, default=RUNS)
    renderer = sub.add_parser("render")
    renderer.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.command == "validate":
        print(json_text(numerical_validation()))
    elif args.command == "render":
        print(json_text(render(args.path)))
    else:
        path, summary = run(args.root)
        print(path)
        print(json_text(summary))


if __name__ == "__main__":
    main()
