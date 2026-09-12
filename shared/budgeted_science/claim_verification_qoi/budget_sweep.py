"""Twelve development claims at 4/2 credits; CPU-only, no new physical systems."""
import argparse
from collections import defaultdict
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import platform
import random

import numpy as np
import scipy

from ..agents.records import RunLog, json_text, read_events, utc_now
from .environment import Backend
from .numerics import config, quote
from .pilot import ROOT, protocol as original_protocol, render_episode, run_episode, source_hashes, summarize
from .policies import _quality, _Session, _record, estimate_claim, run_policy
from .studies import QUANTITIES, validate_study

DEFAULT_SOURCE = ROOT / "demos/claim_verification/runs/20260912T043026Z-qoi-cpu-e6c9d30dd9"
METHODS = ("fixed_rk2_budget", "fixed_euler_budget", "random", "adaptive")
BUDGETS = (4,2)
SELECTION_SEED = 20260912
VERSION = "qoi-small-budget-v1"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def choose_claims(rows):
    """Two valid and two invalid per quantity; never inspect policy outcomes.

    Seeded order after stable physical/config ordering. Within each label stratum,
    prefer two different original physical studies. Insufficient strata fail
    explicitly. No selection by error severity or proximity to a tolerance.
    """
    chosen = []
    for index, quantity in enumerate(QUANTITIES):
        for label in (False,True):
            pool = [r for r in rows if r["cohort"]=="development" and
                    r["seed"] in (7300,7301,7302) and r["claim"]["quantity"]==quantity
                    and r["claim_valid"] is label]
            pool.sort(key=lambda r:(r["seed"],r["profile"],r["claim"]["tolerance"]))
            random.Random(SELECTION_SEED+10*index+int(label)).shuffle(pool)
            used, selected = set(), []
            for row in pool:
                if row["physical_study_id"] not in used:
                    used.add(row["physical_study_id"])
                    selected.append(row)
                if len(selected)==2:
                    break
            if len(selected)!=2:
                raise ValueError(f"insufficient distinct development studies: {quantity}/{label}")
            chosen.extend(deepcopy(selected))
    if len({r["case_id"] for r in chosen})!=12:
        raise ValueError("selection must contain 12 distinct claims")
    return chosen


@lru_cache(maxsize=12)
def _fixed_configuration(budget, quantity, method):
    """Best public error-proxy point on the maximal-output integer-grid frontier.

    Not a truth-selected or proven optimal solver. For each integration step
    count n, use the densest affordable uniform output grid with m intervals.
    Actual quoted cost includes floating-point endpoint handling.
    """
    if isinstance(budget,bool) or budget not in BUDGETS or quantity not in QUANTITIES or method not in ("Euler","RK2"):
        raise ValueError("supported budget, quantity and numerical method required")
    stages = 1 if method=="Euler" else 2
    candidates = []
    for n in range(25,801):
        m = min(800, int(budget*100)-stages*n-1)
        while m>=4:
            cfg = config(method,8/n,8/m,0)
            price = quote(cfg)
            if price["work"]<=int(budget*100):
                candidates.append((_quality(cfg,quantity),price["work"],n,m,cfg))
                break
            m -= 1
    if not candidates:
        raise ValueError("no affordable fixed check")
    _,_,_,_,best = min(candidates,key=lambda r:(r[0],-r[1],r[2],r[3]))
    return best


def fixed_configuration(budget,quantity,method):
    return deepcopy(_fixed_configuration(budget,quantity,method))


def dispatch(call, policy, seed=0):
    if policy in ("random","adaptive"):
        return run_policy(call,policy,seed)
    if policy not in METHODS:
        raise ValueError("unknown policy")
    session = _Session(call)
    description = session.ask("describe",{})
    if description.get("status")!="success":
        raise RuntimeError("public task description unavailable")
    claim, original_id = description["claim"],description["original_run_id"]
    original = description["original_config"]
    read = session.ask("read_run",{"run_id":original_id})
    session.runs[original_id] = _record(read,original_id,original)
    method = "RK2" if policy=="fixed_rk2_budget" else "Euler"
    cfg = fixed_configuration(description["scientific_budget"],claim["quantity"],method)
    # The configuration depends only on public budget, quantity and method.
    # No target evidence, original error, tolerance or private truth selects it.
    price = session.quote(cfg,session.remaining(),reuse=True)
    if price is None:
        raise RuntimeError("budget-matched fixed check unexpectedly unavailable")
    session.purchase(cfg,price,"fixed_budget_matched")
    estimate = estimate_claim(claim,list(session.runs.values()),original_id,original_config=original)
    submission = session.ask("submit",{"verdict":estimate["verdict"],"diagnosis":estimate["diagnosis"],
        "evidence_ids":estimate["evidence_ids"],"justification":estimate["diagnosis"]+
        " Fixed configuration minimizes a public resolution-order proxy, not a certified error bound."})
    return {"policy":policy,"fixed_configuration":cfg,"estimator":estimate,
            "acquisitions":session.acquisitions,"trace":session.trace,"submission":submission}


def _catalog(source):
    source = Path(source).resolve()
    catalog = json.loads((source/"catalog.json").read_text(encoding="utf-8"))
    selected = choose_claims(catalog["studies"])
    studies, hashes = [], {}
    for row in selected:
        file = source/"private/studies"/(row["case_id"]+".json")
        study = validate_study(json.loads(file.read_text(encoding="utf-8")))
        if (study["case_id"]!=row["case_id"] or study["claim"]!=row["claim"]
                or study["physical_study_id"]!=row["physical_study_id"]
                or any(study["private"][k]!=row[k] for k in study["private"])):
            raise ValueError("catalog and selected study disagree")
        studies.append(study)
        hashes[row["case_id"]] = sha(file)
    return studies, selected, hashes


def aggregate(rows):
    groups = defaultdict(list)
    for row in rows:
        for scope in ("all",row["claim"]["quantity"]):
            groups[(row["budget"],row["policy"],scope)].append(row)
    return [{"budget":budget,"policy":policy,"scope":scope,**summarize(part)}
            for (budget,policy,scope),part in sorted(groups.items())]


def render(path):
    """Only saved files are read: no policy, solver, or API calls."""
    path = Path(path).resolve()
    manifest = json.loads((path/"manifest.json").read_text(encoding="utf-8"))
    rows = []
    for directory in sorted((path/"episodes").glob("*")):
        if not directory.is_dir():
            continue
        meta = json.loads((directory/"manifest.json").read_text(encoding="utf-8"))
        row,corrupt = None,False
        if (directory/"result.json").exists():
            try:
                row = json.loads((directory/"result.json").read_text(encoding="utf-8"))
            except (json.JSONDecodeError,UnicodeDecodeError):
                corrupt = True
        if corrupt:
            (directory/"transcript.md").write_text(
                "# Interrupted CPU episode\n\nThe result JSON is incomplete or corrupt and has been preserved. "
                "See [chronological events](events.jsonl) and [original artifacts](public_artifacts.json). "
                "This episode is scored incomplete.\n",encoding="utf-8")
        else:
            render_episode(directory)
        if row is None:
            study = next(r for r in manifest["selected_claims"] if r["case_id"]==meta["case_id"])
            events,torn = read_events(directory)
            charges,pending = {},set()
            for e in events:
                if e["kind"]=="work_reserved": pending.add(e["entry"]["run_id"])
                if e["kind"]=="work_charged":
                    charges[e["entry"]["run_id"]]=e["entry"]["work"]
                    pending.discard(e["entry"]["run_id"])
            row = {"case_id":study["case_id"],"claim":study["claim"],"policy":meta["policy"],
                "claim_valid":study["claim_valid"],"correct":False,"covered":False,"incomplete":True,
                "false_accept":False,"false_reject":False,"abstained":False,"seconds":None,
                "spent":None if pending or torn else sum(charges.values())/100,"path":str(directory),"verdict":None,
                "corrupt_result":corrupt}
        row["budget"] = meta["budget"]
        rows.append(row)
    events,torn = read_events(path)
    interruptions = [e for e in events if e["kind"]=="sweep_interrupted"]
    expected = {(s["case_id"],b,p) for s in manifest["selected_claims"] for b in manifest["budgets"] for p in manifest["methods"]}
    actual = [(r["case_id"],r["budget"],r["policy"]) for r in rows]
    completed = any(e["kind"]=="sweep_completed" for e in events)
    summary = {"claim_count":len(manifest["selected_claims"]),"episodes":len(rows),"expected_episodes":len(expected),
        "completed":completed and not interruptions and not torn and len(actual)==len(expected) and set(actual)==expected
                    and not any(r.get("corrupt_result") for r in rows),
        "source_freeze_verified_at_completion":completed,"interruptions":interruptions,"torn_root_event":torn,
        "missing_slots":[list(x) for x in sorted(expected-set(actual))],"duplicate_slots":len(actual)-len(set(actual)),
        "unknown_spending_count":sum(r["spent"] is None for r in rows),
        "corrupt_result_count":sum(r.get("corrupt_result",False) for r in rows),"api_expenditure":0,"summaries":aggregate(rows)}
    (path/"summary.json").write_text(json_text(summary)+"\n",encoding="utf-8")
    lines = ["# Twelve-claim development budget sweep", "",
        "Four policies at two budgets on the same 12 development claims. No API calls or fresh-system evaluation.","",
        f"Completed: {summary['completed']}; recorded/expected: {len(rows)}/{len(expected)}; unknown spending: {summary['unknown_spending_count']}.","",
        "| Credits | Policy | Quantity | Correct | False accept | False reject | Incomplete | Mean spent |",
        "|---:|---|---|---:|---:|---:|---:|---:|"]
    for s in summary["summaries"]:
        cost = "unknown" if s["mean_credits"] is None else f"{s['mean_credits']:.3f}"
        lines.append(f"| {s['budget']} | {s['policy']} | {s['scope']} | {s['correct']}/{s['n']} | {s['false_accept']} | {s['false_reject']} | {s['incomplete']} | {cost} |")
    lines += ["","## Every attempted episode","","| Claim | Budget | Policy | Verdict | Correct | Transcript |",
              "|---|---:|---|---|---:|---|"]
    for r in rows:
        relative = Path(r["path"]).relative_to(path).as_posix()
        lines.append(f"| {r['case_id']} | {r['budget']} | {r['policy']} | {r.get('verdict')} | {r['correct']} | [trace]({relative}/transcript.md) |")
    (path/"report.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    return summary


def run(source=DEFAULT_SOURCE,root=None):
    source = Path(source).resolve()
    studies,selected,hashes = _catalog(source)
    log = RunLog(root or ROOT/"demos/claim_verification/runs","qoi-low-budget")
    provenance = source_hashes()
    settings = original_protocol()
    tables = [{"budget":b,"quantity":q,"method":m,"config":fixed_configuration(b,q,m),
               "quote":quote(fixed_configuration(b,q,m))}
              for b in BUDGETS for q in QUANTITIES for m in ("RK2","Euler")]
    manifest = {"version":VERSION,"frozen_at":utc_now(),"source_catalog":str(source),
        "catalog_sha256":sha(source/"catalog.json"),"imported_study_hashes":hashes,
        "selected_claims":selected,"selection_seed":SELECTION_SEED,
        "selection_rule":"2 valid + 2 invalid per quantity, shuffled within development labels; distinct studies within each label; no baseline results read",
        "budgets":list(BUDGETS),"methods":list(METHODS),"policy_seed":0,
        "fixed_configurations":tables,"source_hashes":provenance,"api_expenditure":0,
        "limits":{"episode_seconds":settings["episode_seconds"],"max_tool_requests":settings["max_tool_requests"]},
        "software":{"python":platform.python_version(),"numpy":np.__version__,"scipy":scipy.__version__}}
    log.write_json("manifest.json",manifest)
    for s in studies:
        log.write_json(f"private/studies/{s['case_id']}.json",s)
    print(f"Frozen 12-claim CPU sweep: {log.path}",flush=True)
    try:
        backend = Backend()
        for budget in BUDGETS:
            for i,study in enumerate(studies):
                if source_hashes()!=provenance:
                    raise RuntimeError("source changed after freeze")
                for method in METHODS:
                    log.event("episode_started",case_id=study["case_id"],budget=budget,policy=method)
                    result = run_episode(study,method,0,{**settings,"budget":budget},backend,
                                         log.path/"episodes",policy_runner=dispatch)
                    log.event("episode_finished",case_id=study["case_id"],budget=budget,policy=method,
                              path=result["path"],correct=result["correct"],incomplete=result["incomplete"])
                print(f"Budget {budget}: completed {i+1}/12 claims x 4 policies",flush=True)
        if source_hashes()!=provenance:
            raise RuntimeError("source changed during final episode")
        log.event("sweep_completed",episodes=96)
    except BaseException as exc:
        log.event("sweep_interrupted",error={"class":type(exc).__name__,"message":str(exc)})
        raise
    finally:
        log.close()
        render(log.path)
    print(f"Report: {log.path/'report.md'}",flush=True)
    return log.path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=("run","render"))
    parser.add_argument("path",nargs="?")
    parser.add_argument("--source",default=str(DEFAULT_SOURCE))
    args = parser.parse_args()
    if args.command=="render":
        if not args.path: parser.error("render needs a saved run path")
        print(json_text(render(args.path)))
    else:
        run(args.source,args.path)


if __name__=="__main__":
    main()
