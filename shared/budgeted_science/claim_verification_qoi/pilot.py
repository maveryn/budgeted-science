"""Frozen CPU-only pilot and offline rendering; no agent transport or credentials."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import platform
from statistics import mean
from time import perf_counter
from uuid import uuid4

import numpy as np
import scipy

from ..agents.records import RunLog, json_text, read_events, utc_now
from . import VERSION
from .environment import Backend, Episode
from .numerics import BOUNDS, config, reference, solve
from .studies import QUANTITIES, TOLERANCES, make_study

ROOT = Path(__file__).resolve().parents[3]
POLICIES = ("fixed_rk2", "fixed_euler", "fixed_dense_output", "random", "adaptive")


def protocol():
    return {"version": VERSION, "cohorts": {"development": list(range(7300,7303)),
            "fresh": list(range(7400,7406))}, "bounds": [list(v) for v in BOUNDS],
            "original_profiles": [config("Euler", .16, .4, 0),
                                  config("Euler", .04, .8, .25),
                                  config("RK2", .16, .4, .5)],
            "quantities": list(QUANTITIES), "tolerances": deepcopy(TOLERANCES),
            "policies": list(POLICIES), "budget": 8, "policy_seed": 0,
            "policy_seed_rule": "fixed 0 for every case; independent of hidden identity, shared across matched claims",
            "work_proxy": "(RHS evaluations + recorded output samples)/100 credits",
            "max_tool_requests": 2000, "episode_seconds": 300,
            "selection": "all fixed profiles; no error/label/policy-based selection; ineligible peak times omitted",
            "scoring": "printed original quantity within its relative or absolute tolerance",
            "api_expenditure": 0}


def source_hashes():
    package = Path(__file__).resolve().parents[1]
    paths = list(Path(__file__).parent.glob("*.py"))
    paths += list((package / "resource_planning").glob("*.py"))
    paths += [package / "claim_verification" / "numerics.py", package / "agents" / "records.py"]
    return {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(set(paths))}


def target(seed):
    bounds = np.asarray(BOUNDS)
    return np.random.default_rng(seed).uniform(bounds[:,0], bounds[:,1]).tolist()


def build_catalog(settings, log):
    studies, omitted, references, original_failures = [], [], {}, []
    for cohort, seeds in settings["cohorts"].items():
        for seed in seeds:
            theta = target(seed)
            ref = reference(theta)
            references[str(seed)] = {"theta":theta, "cohort":cohort, **ref}
            log.write_json(f"private/references/{seed}.json", references[str(seed)])
            for p, cfg in enumerate(settings["original_profiles"]):
                physical_id = "physical-" + uuid4().hex
                run = solve(theta, cfg)
                log.write_json(f"private/originals/{seed}-{p}.json", run)
                if run["status"] != "success":
                    original_failures.append({"seed":seed, "profile":p, "cohort":cohort, "config":cfg})
                    continue
                for q, quantity in enumerate(settings["quantities"]):
                    kind, tolerances = settings["tolerances"][quantity]
                    if quantity == "peak_time" and not ref["peak_time_eligible"]:
                        omitted.append({"seed":seed, "profile":p, "cohort":cohort,
                                        "quantity":quantity, "tolerances":list(tolerances),
                                        "reason":ref["peak_time_reason"]})
                        continue
                    for tolerance in tolerances:
                        study = make_study(seed,theta,cohort,p,run,ref,quantity,tolerance,
                                           (seed+p+q)%3, physical_id)
                        studies.append(study)
                        log.write_json(f"private/studies/{study['case_id']}.json", study)
                        log.write_json(f"public/{study['case_id']}/artifacts.json", study["artifacts"])
                        log.event("study_generated", case_id=study["case_id"], cohort=cohort)
    catalog = {"studies": [{"case_id":s["case_id"], "physical_study_id":s["physical_study_id"],
                "claim":s["claim"], **s["private"]} for s in studies],
               "omitted_timing":omitted, "failed_originals":original_failures,
               "references":references}
    log.write_json("catalog.json", catalog)
    return studies, catalog


def run_episode(study, policy, seed, settings, backend, root, *, policy_runner=None):
    from .policies import run_policy
    run_policy = policy_runner or run_policy
    log = RunLog(root, policy)
    start = perf_counter()
    episode = Episode(study, settings["budget"], backend, log.event)
    log.write_json("manifest.json", {"case_id":study["case_id"], "policy":policy,
                   "policy_seed":seed, "api_expenditure":0, "budget":settings["budget"]})
    log.write_json("public_artifacts.json", study["artifacts"])
    count = 0

    def call(name, arguments=None):
        nonlocal count
        if perf_counter()-start > settings["episode_seconds"]:
            episode.state, episode.reason = "aborted", "CPU episode deadline"
            raise TimeoutError("CPU episode deadline")
        if count >= settings["max_tool_requests"]:
            raise RuntimeError("CPU tool-request limit")
        count += 1
        response = episode.tools.call(name, arguments or {}, f"cpu-{count:04d}")
        if perf_counter()-start > settings["episode_seconds"]:
            episode.state, episode.reason = "aborted", "CPU episode deadline"
            raise TimeoutError("CPU episode deadline")
        return response

    diagnostics = None
    interrupted = False
    try:
        diagnostics = run_policy(call, policy, seed=seed)
        if perf_counter()-start > settings["episode_seconds"]:
            episode.state, episode.reason = "aborted", "CPU episode deadline"
        episode.abort("policy ended without submission")
    except (KeyboardInterrupt, SystemExit) as exc:
        episode.abort(type(exc).__name__)
        interrupted = True
    except Exception as exc:
        episode.abort(f"{type(exc).__name__}: {exc}")
        log.event("policy_failed", error={"class":type(exc).__name__, "message":str(exc)})
    result = {**episode.evaluate(), "cohort":study["private"]["cohort"],
              "target_seed":study["private"]["seed"], "physical_study_id":study["physical_study_id"],
              "claim":study["claim"], "original_config":study["run"]["config"],
              "policy":policy, "policy_seed":seed, "seconds":perf_counter()-start,
              "tool_requests":count, "ledger":episode.ledger, "submission":episode.submission,
              "diagnostics":diagnostics, "api_expenditure":0, "path":str(log.path)}
    # Publish a complete final result atomically; interrupted temporary files
    # must not masquerade as a readable completed result during offline review.
    log.write_json("result.json", result, replace=True)
    log.event("episode_finished", evaluation=episode.evaluate())
    log.close()
    render_episode(log.path)
    if interrupted:
        raise KeyboardInterrupt(f"preserved interrupted episode {log.path}")
    return result


def summarize(rows):
    if not rows:
        return {"n":0}
    credits = [r["spent"] for r in rows if r["spent"] is not None]
    seconds = [r["seconds"] for r in rows if r["seconds"] is not None]
    return {"n":len(rows), "correct":sum(r["correct"] for r in rows),
            "valid_claims":sum(r["claim_valid"] for r in rows),
            "covered":sum(r["covered"] for r in rows),
            "false_accept":sum(r["false_accept"] for r in rows),
            "false_reject":sum(r["false_reject"] for r in rows),
            "abstained":sum(r["abstained"] for r in rows),
            "incomplete":sum(r["incomplete"] for r in rows),
            "mean_credits":mean(credits) if credits else None, "known_credit_count":len(credits),
            "mean_seconds":mean(seconds) if seconds else None, "known_runtime_count":len(seconds)}


def aggregate(rows, catalog):
    groups = defaultdict(list)
    for row in rows:
        c = row["claim"]
        for scope in ("all", c["quantity"], f"{c['quantity']}:{c['tolerance']:g}"):
            groups[(row["cohort"],scope,row["policy"])].append(row)
    summaries = [{"cohort":cohort, "scope":scope, "policy":policy, **summarize(part)}
                 for (cohort,scope,policy),part in sorted(groups.items())]
    contrasts = []
    physical = defaultdict(list)
    for study in catalog["studies"]:
        physical[study["physical_study_id"]].append(study)
    for key, studies in physical.items():
        contrasts.append({"physical_study_id":key, "cohort":studies[0]["cohort"],
                          "seed":studies[0]["seed"], "mixed_labels":len({s["claim_valid"] for s in studies})>1,
                          "claims":[{"quantity":s["claim"]["quantity"], "tolerance":s["claim"]["tolerance"],
                                     "valid":s["claim_valid"], "normalized_error":s["normalized_error"]}
                                    for s in studies]})
    return {"episodes":len(rows), "summaries":summaries, "same_study_contrasts":contrasts,
            "api_expenditure":0, "original_failures":catalog["failed_originals"],
            "omitted_timing":catalog["omitted_timing"]}


def render_episode(path):
    """Saved JSON/JSONL only. No solver, tool, policy, or API execution."""
    path = Path(path)
    events, torn = read_events(path)
    lines = ["# CPU claim-verification transcript", "", "Scripted numerical policy, not an LLM.", ""]
    if torn:
        lines += ["Warning: interrupted final event line preserved.", ""]
    public = path / "public_artifacts.json"
    if public.exists():
        lines += ["## Original public artifacts", "", "```json", public.read_text(encoding="utf-8"), "```", ""]
    for e in events:
        if e["kind"] in ("tool_requested", "tool_result", "policy_failed"):
            lines += [f"## {e['sequence']}: {e['kind']}", "", "```json", json_text(e), "```", ""]
        elif e["kind"] == "numerical_artifact":
            lines += [f"Numerical artifact `{e['run_id']}` is preserved in events.jsonl (event {e['sequence']}).", ""]
    if (path / "result.json").exists():
        result = json.loads((path / "result.json").read_text(encoding="utf-8"))
        lines += ["## Private evaluation", "", "```json", json_text({k:v for k,v in result.items()
                   if k not in ("diagnostics","ledger")}), "```", ""]
    (path / "transcript.md").write_text("\n".join(lines), encoding="utf-8")


def render(path):
    """Regenerate reports from saved episodes; incomplete attempts remain visible."""
    path = Path(path).resolve()
    catalog = json.loads((path / "catalog.json").read_text(encoding="utf-8"))
    rows = []
    for episode in sorted((path / "episodes").glob("*")):
        if not episode.is_dir():
            continue
        render_episode(episode)
        if (episode / "result.json").exists():
            rows.append(json.loads((episode / "result.json").read_text(encoding="utf-8")))
        else:
            meta = json.loads((episode / "manifest.json").read_text(encoding="utf-8"))
            s = next(s for s in catalog["studies"] if s["case_id"]==meta["case_id"])
            events, torn = read_events(episode)
            charges, pending = {}, set()
            for e in events:
                if e["kind"] == "work_reserved":
                    pending.add(e["entry"]["run_id"])
                elif e["kind"] == "work_charged":
                    key = e["entry"]["run_id"]
                    charges[key] = e["entry"]["work"]
                    pending.discard(key)
            spent = None if pending or torn else sum(charges.values())/100
            rows.append({"case_id":s["case_id"], "claim":s["claim"], "cohort":s["cohort"],
                         "policy":meta["policy"], "claim_valid":s["claim_valid"], "correct":False,
                         "covered":False,"false_accept":False,"false_reject":False,"abstained":False,
                         "incomplete":True,"spent":spent,"seconds":None,"path":str(episode),
                         "accounting_unknown":spent is None})
    summary = aggregate(rows,catalog)
    summary["accounting_unknown"] = sum(r.get("accounting_unknown",False) for r in rows)
    root_events, torn = read_events(path)
    complete = any(e["kind"]=="pilot_completed" for e in root_events)
    interrupted = [e for e in root_events if e["kind"]=="pilot_interrupted"]
    manifest = json.loads((path/"manifest.json").read_text(encoding="utf-8")) if (path/"manifest.json").exists() else {}
    expected = len(catalog["studies"])*len(manifest.get("protocol",{}).get("policies",POLICIES))
    keys = [(r["case_id"],r["policy"]) for r in rows]
    freeze_valid = (True if complete else False if any("source changed" in e["error"]["message"] for e in interrupted) else None)
    summary["completion"] = {"completed":complete and not interrupted and not torn,
        "source_freeze_verified_at_completion":freeze_valid,"expected_episodes":expected,
        "recorded_episodes":len(rows),"duplicate_slots":len(keys)-len(set(keys)),
        "interruptions":interrupted,"torn_root_event":torn}
    (path / "summary.json").write_text(json_text(summary)+"\n",encoding="utf-8")
    lines = ["# Claim-specific predator-prey CPU pilot", "", "No model/API calls. Objective printed-value scoring.", "",
             "Claims share underlying systems and original studies; they are not independent scientific systems.", "",
             f"Completion: {summary['completion']}. Unknown expenditure episodes: {summary['accounting_unknown']}.", "",
             f"{len(catalog['studies'])} claims; {len(rows)} attempted episodes. "
             f"Omitted timing profile-groups: {len(catalog['omitted_timing'])}; failed originals: {len(catalog['failed_originals'])}.", "",
             "| Cohort | Claim | Policy | Correct | False accept | False reject | Abstain | Incomplete | Mean credits |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for s in summary["summaries"]:
        lines.append(f"| {s['cohort']} | {s['scope']} | {s['policy']} | {s['correct']}/{s['n']} | "
                     f"{s['false_accept']} | {s['false_reject']} | {s['abstained']} | {s['incomplete']} | {_display(s['mean_credits'])} |")
    lines += ["", "## Individual results", "", "| Case | Policy | Correct | Spent | Transcript |",
              "|---|---|---:|---:|---|"]
    for r in rows:
        relative = Path(r["path"]).relative_to(path).as_posix()
        lines.append(f"| {r['case_id']} | {r['policy']} | {r['correct']} | {_display(r['spent'])} | [trace]({relative}/transcript.md) |")
    lines += ["", "Numerical baselines receive structured claims. No explanation, diagnosis, or confidence grading. "
              "Pricing is synthetic work accounting, not runtime or money. No adaptive advantage is presumed.", ""]
    (path / "report.md").write_text("\n".join(lines),encoding="utf-8")
    return summary


def _display(value):
    return "unavailable" if value is None else f"{value:.3f}"


def run(root=None, development_only=False):
    settings = protocol()
    if development_only:
        settings["cohorts"] = {"development":settings["cohorts"]["development"]}
    log = RunLog(root or ROOT/"demos/claim_verification/runs", "qoi-cpu")
    hashes = source_hashes()
    log.write_json("manifest.json", {"frozen_at":utc_now(), "protocol":settings,
                   "source_hashes":hashes, "software":{"python":platform.python_version(),
                   "numpy":np.__version__, "scipy":scipy.__version__}, "api_expenditure":0})
    print(f"Frozen CPU pilot: {log.path}", flush=True)
    try:
        studies, catalog = build_catalog(settings,log)
        print(f"Generated {len(studies)} claims; {len(catalog['omitted_timing'])} timing omissions",flush=True)
        backend = Backend()
        for i,study in enumerate(studies):
            if source_hashes() != hashes:
                raise RuntimeError("source changed after protocol freeze; pilot halted")
            for policy in settings["policies"]:
                log.event("episode_started",case_id=study["case_id"],policy=policy,index=i)
                result = run_episode(study,policy,settings["policy_seed"],settings,backend,log.path/"episodes")
                log.event("episode_finished",case_id=study["case_id"],policy=policy,
                          path=result["path"],correct=result["correct"],incomplete=result["incomplete"])
            if (i+1)%6==0:
                print(f"Completed {i+1}/{len(studies)} claims x {len(settings['policies'])} policies",flush=True)
        if source_hashes()!=hashes:
            raise RuntimeError("source changed during final episode")
        log.event("pilot_completed",claims=len(studies),episodes=len(studies)*len(settings["policies"]))
    except BaseException as exc:
        log.event("pilot_interrupted",error={"class":type(exc).__name__,"message":str(exc)})
        raise
    finally:
        log.close()
        if (log.path/"catalog.json").exists():
            render(log.path)
    print(f"Report: {log.path/'report.md'}",flush=True)
    return log.path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=("validate","run","render"))
    parser.add_argument("path",nargs="?")
    parser.add_argument("--development-only",action="store_true")
    args = parser.parse_args()
    if args.command=="render":
        if not args.path:
            parser.error("render requires a saved run path")
        print(json_text(render(args.path)))
    elif args.command=="validate":
        print(json_text(reference([1,.08,1.4])))
    else:
        run(args.path,args.development_only)


if __name__=="__main__":
    main()
