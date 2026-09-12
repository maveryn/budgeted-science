"""Freeze, commission, evaluate, and render the CPU-only incremental pilot."""
import argparse
from copy import deepcopy
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
from time import monotonic

import numpy as np

from ..agents.records import RunLog, digest, json_text
from ..claim_verification.numerics import Backend, BOUNDS, configuration, output_grid, peak, reference
from ..claim_verification.studies import make_study, make_artifacts
from . import VERSION
from .environment import IncrementalEpisode, bisect_times
from .policies import run_policy

ROOT = Path(__file__).resolve().parents[3]
SEEDS = tuple(range(7100, 7106))
# Frozen numerical configurations, NOT truth-selected difficulty categories.
PROFILES = (("fine", .005, .25, .25), ("integration_coarse", .08, .25, .25),
            ("sampling_coarse", .01, 2., .25), ("mixed_moderate", .04, 1., .5),
            ("mixed_coarse", .08, 2., .5))
POLICIES = ("fixed_IIS", "fixed_ISS", "random", "adaptive_change")
BUDGET = 8
DIAGNOSTIC_BUDGETS = (8, 10, 12)
PROMPT = """Audit the completed study's original 5% peak-accuracy claim.
You have 8 credits. Integration refinement halves the current Euler timestep
for 3 credits; sampling refinement bisects every stored-output interval for
2 credits, retaining the integration settings. Each is an incremental check,
not a direct high-accuracy reference. Inspection, comparison and retrieval are
free. Reusing a purchased configuration is free. Submit ACCEPT, REJECT or
ABSTAIN about the original claim. No savings bonus or full-budget requirement.
This CPU pilot executes named numerical policies, not an LLM.
"""


def source_provenance():
    files = list(Path(__file__).parent.glob("*.py"))
    files += list((ROOT / "shared/budgeted_science/claim_verification").glob("*.py"))
    files += [ROOT / "shared/budgeted_science/resource_planning/environment.py",
              ROOT / "shared/budgeted_science/resource_planning/config.py",
              ROOT / "shared/budgeted_science/agents/records.py"]
    hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    return {"source_hashes": hashes, "source_manifest_hash": digest(hashes),
            "versions": {"python": platform.python_version(), "numpy": version("numpy"), "scipy": version("scipy")}}


def refine_config(config, i, s):
    result = deepcopy(config)
    result["dt"] /= 2 ** i
    for _ in range(s):
        result["output_times"] = bisect_times(result["output_times"])
    return result


def check_diagnostic(study, q):
    ref, reported = study["private"]["reference_q"], study["reported_q"]
    difference = abs(q - ref)
    # D(q)=|reported-q|-0.05*q is 1.05-Lipschitz for positive q.
    # This private check tests whether the reference-measured residual is below
    # the distance to the verdict boundary. It is NOT an agent-visible bound.
    margin = abs(abs(reported - ref) - .05 * ref)
    return {"relative_error": difference / ref, "within_one_percent": difference / ref <= .01,
            "margin_resolving": bool(1.05 * difference < margin),
            "direct_verdict": "ACCEPT" if abs(reported-q)/abs(q) <= .05 else "REJECT"}


def commission(log, backend):
    studies, failures, cells = [], [], []
    bounds = np.asarray(BOUNDS)
    for system_index, seed in enumerate(SEEDS):
        theta = np.random.default_rng(seed).uniform(bounds[:, 0], bounds[:, 1])
        ref = reference(theta)
        log.write_json(f"private/references/{seed}.json", {"theta": theta.tolist(), **ref})
        for profile_index, (profile, dt, spacing, phase) in enumerate(PROFILES):
            config = configuration("Euler", dt=dt, times=output_grid(spacing, phase))
            run, _ = backend.get(theta, config)
            if run["status"] != "success":
                failure = {"seed": seed, "profile": profile, "status": "initial_run_failed"}
                failures.append(failure); log.event("commissioning_failure", **failure)
                continue
            identity = VERSION + ":" + digest(config)[:16]
            study = make_study(seed, theta, identity, run, ref, (system_index + profile_index) % 3)
            study["private"].update(profile=profile, category=profile, incremental_version=VERSION)
            study["artifacts"] = make_artifacts(study)
            studies.append(study)
            log.write_json(f"private/studies/{study['case_id']}.json", study)
            log.write_json(f"public/{study['case_id']}.json", study["artifacts"])
            for i in range(max(DIAGNOSTIC_BUDGETS)//3 + 1):
                for s in range(max(DIAGNOSTIC_BUDGETS)//2 + 1):
                    cost = 3*i+2*s
                    if cost > max(DIAGNOSTIC_BUDGETS):
                        continue
                    candidate, _ = backend.get(theta, refine_config(config, i, s))
                    cell = {"case_id": study["case_id"], "i": i, "s": s, "cost": cost,
                            "status": candidate["status"]}
                    if candidate["status"] == "success":
                        q = peak(candidate)["q"]
                        cell.update(q=q, **check_diagnostic(study, q))
                    cells.append(cell)
            log.event("study_commissioned", case_id=study["case_id"], profile=profile,
                      original_error=study["private"]["relative_error"], claim_valid=study["private"]["claim_valid"])
        print(f"Commissioned system {seed}: {len(studies)} studies", flush=True)
    log.write_json("private/catalog.json", {"studies": studies, "failures": failures,
                   "complete": len(studies)==len(SEEDS)*len(PROFILES) and not failures})
    log.write_json("private/reachable_checks.json", cells)
    return studies, failures, cells


def evaluate_policy(log, study, policy, index, backend, *, estimator="last_run"):
    prefix = f"episodes/{index:03d}"
    def record(kind, **data):
        if kind == "numerical_artifact":
            artifact = data.pop("artifact")
            data["artifact_path"] = log.write_json(f"{prefix}/{data['run_id']}.json", artifact)
        log.event("episode_event", episode=index, event_kind=kind, **data)
    episode = IncrementalEpisode(study, backend=backend, log=record)
    count, start = 0, monotonic()
    log.write_json(f"{prefix}/prompt.json", {"text": PROMPT, "case_id": study["case_id"], "policy": policy})
    def call(name, args):
        nonlocal count
        if count >= 30 or monotonic()-start >= 300:
            raise TimeoutError("CPU policy request/time limit")
        count += 1
        return episode.tools.call(name, args, f"policy-{count}")
    diagnostics = None
    try:
        # Substream based only on fixed case order, never observations or labels.
        seed = 10000 + index // len(POLICIES)
        diagnostics = run_policy(call, policy, seed, estimator=estimator)
    except Exception as exc:
        episode.abort("CPU policy failure")
        log.event("policy_failure", episode=index, error=log.redactor.error(exc))
    evaluation = episode.evaluate()
    expected = "ACCEPT" if study["private"]["claim_valid"] else "REJECT"
    alt = diagnostics["extrapolated_verdict"] if diagnostics else None
    row = {"episode": index, "case_id": study["case_id"], "profile": study["private"]["profile"],
           "system_seed": study["private"]["seed"], "policy": policy,
           "evaluation": evaluation, "diagnostics": diagnostics,
           "extrapolated_verdict": alt, "extrapolated_correct": alt == expected,
           "runtime_seconds": monotonic()-start, "tool_requests": count}
    log.write_json(f"{prefix}/result.json", row)
    log.event("policy_finished", **row)
    return row


def render(path):
    path = Path(path)
    manifest = json.loads((path/"manifest.json").read_text(encoding="utf-8"))
    catalog = json.loads((path/"private/catalog.json").read_text(encoding="utf-8"))
    cells = json.loads((path/"private/reachable_checks.json").read_text(encoding="utf-8"))
    studies = catalog["studies"]
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((path/"episodes").glob("*/result.json"))]
    summary = {"studies": len(studies), "commissioning_failures": catalog["failures"],
        "valid_claims": sum(s["private"]["claim_valid"] for s in studies),
        "invalid_claims": sum(not s["private"]["claim_valid"] for s in studies),
        "scientific_budget": manifest["budget"], "api_calls": 0, "policies": {}, "reachability": {}}
    for policy in manifest["policies"]:
        selected = [r for r in rows if r["policy"]==policy]
        e = [r["evaluation"] for r in selected]
        summary["policies"][policy] = {"episodes": len(selected), "direct_correct": sum(x["correct"] for x in e),
            "extrapolated_correct": sum(r["extrapolated_correct"] for r in selected),
            "extrapolation_available": sum(r["extrapolated_verdict"] is not None for r in selected),
            "false_accept": sum(x["false_accept"] for x in e), "false_reject": sum(x["false_reject"] for x in e),
            "abstentions": sum(x["abstained"] for x in e), "incomplete": sum(x["incomplete"] for x in e),
            "credits": sum(x["spent"] for x in e),
            "actions": {"".join(r["diagnostics"]["actions"]):sum(1 for v in selected if v["diagnostics"] and v["diagnostics"]["actions"]==r["diagnostics"]["actions"])
                        for r in selected if r["diagnostics"]}}
    for budget in manifest["diagnostic_budgets"]:
        available = [c for c in cells if c["cost"]<=budget and c["status"]=="success"]
        ids = {s["case_id"] for s in studies}
        resolving = {c["case_id"] for c in available if c["margin_resolving"]}
        precise = {c["case_id"] for c in available if c["within_one_percent"]}
        summary["reachability"][str(budget)] = {"margin_resolving_cases":len(resolving),
            "within_one_percent_cases":len(precise), "unresolved_case_ids":sorted(ids-resolving)}
    # Fixed endpoint table includes every affordable allocation, not an optimal-policy claim.
    endpoints=[]
    for i,s in sorted({(c['i'],c['s']) for c in cells if c['cost']<=manifest['budget']}):
        selected=[c for c in cells if c['i']==i and c['s']==s]
        truth={x['case_id']:('ACCEPT' if x['private']['claim_valid'] else 'REJECT') for x in studies}
        endpoints.append({'i':i,'s':s,'cost':3*i+2*s,
            'correct':sum(c.get('direct_verdict')==truth[c['case_id']] for c in selected),
            'margin_resolving':sum(c.get('margin_resolving',False) for c in selected)})
    summary['fixed_endpoints']=endpoints
    (path/"summary.json").write_text(json_text(summary)+"\n",encoding="utf-8")
    lines=["# Incremental claim-verification CPU pilot", "", "Development calibration; no LLM/API calls.",
           f"Studies: {len(studies)} on {len(manifest['seeds'])} related systems. Budget: {manifest['budget']}; integration costs 3, sampling 2.",
           "Original claim tolerance remains 5%. All originals use Euler; each paid check is one halving.", "",
           "## Numerical policies", "", "| Policy | Episodes | Last-run correct | Extrapolated correct | Credits | Incomplete |",
           "|---|---:|---:|---:|---:|---:|"]
    for name,r in summary['policies'].items():
        lines.append(f"| {name} | {r['episodes']} | {r['direct_correct']} | {r['extrapolated_correct']} | {r['credits']:g} | {r['incomplete']} |")
    lines += ["", "Extrapolation uses the SAME purchased values, assumes first-order integration and second-order sampling, "
              "and is neither a certified bound nor a truth-selected answer. It is scored as a separate estimator sensitivity check.", "",
              "## Private reachability diagnostic", "", "| Budget | Reference-audited margin-resolving check reachable | <=1% check reachable |",
              "|---|---:|---:|"]
    for b,r in summary['reachability'].items():
        lines.append(f"| {b} | {r['margin_resolving_cases']}/{len(studies)} | {r['within_one_percent_cases']}/{len(studies)} |")
    lines += ["", "These use hidden references to inspect affordable endpoints. They are NOT a usable policy, a certified "
              "agent confidence measure, or proof that extrapolation cannot succeed when no sufficiently refined run is affordable.", "",
              "## Every fixed affordable endpoint", "", "| Integration halvings | Sampling halvings | Cost | Correct direct verdicts | Resolving checks |",
              "|---:|---:|---:|---:|---:|"]
    for r in endpoints:
        lines.append(f"| {r['i']} | {r['s']} | {r['cost']} | {r['correct']} | {r['margin_resolving']} |")
    lines += ["", "## Case and policy results", "", "| Case | Profile | Policy | Direct verdict | Correct | Extrapolated correct | Trace |",
              "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['case_id']} | {r['profile']} | {r['policy']} | {r['evaluation']['verdict']} | {r['evaluation']['correct']} | {r['extrapolated_correct']} | [Record](episodes/{r['episode']:03d}/result.json) |")
    lines += ["", "Full chronological calls/responses and charges: [events.jsonl](events.jsonl). "
              "Private references and reachability results are separate from public study artifacts.", ""]
    (path/"report.md").write_text("\n".join(lines),encoding="utf-8")
    return summary


def run(root):
    log=RunLog(root,"incremental-cpu")
    log.write_json('manifest.json',{'version':VERSION, 'seeds':SEEDS,'profiles':PROFILES,'budget':BUDGET,
        'diagnostic_budgets':DIAGNOSTIC_BUDGETS,'policies':POLICIES,'random_seed_rule':'10000 + case ordinal',
        'selection':'fixed configuration grid; no selection on labels or policy outcomes',
        'api_calls':0, 'api_usd':0, **source_provenance()})
    print(log.path,flush=True)
    try:
        backend=Backend()
        studies, failures, _=commission(log,backend)
        for index,study in enumerate(studies):
            for j,policy in enumerate(POLICIES):
                evaluate_policy(log,study,policy,index*len(POLICIES)+j,backend)
            print(f"Evaluated {index+1}/{len(studies)} studies",flush=True)
        summary=render(log.path)
        log.event('pilot_finished',summary=summary)
        print(json_text(summary),flush=True)
    finally:
        log.close()
    return log.path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('run'); p.add_argument('--output-root',type=Path,default=ROOT/'demos/claim_verification/runs')
    p=sub.add_parser('render'); p.add_argument('path',type=Path)
    args=parser.parse_args()
    if args.command=='run': run(args.output_root)
    else: print(json_text(render(args.path)))
