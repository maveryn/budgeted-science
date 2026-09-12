"""Six existing MMS studies, two menus, twelve fresh Luna episodes; $2 total."""
import argparse
import asyncio
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import statistics

from ..mms_verification.alternatives import AlternativeAudit, EXTRA_ACTIONS, VERSION
from ..mms_verification.environment import Audit, score
from ..mms_verification.experiment import ROOT, RUNS, artifact_hashes
from ..mms_verification.policies import run_policy
from .mms_catalog import CATALOG, read_catalog
from .mms_verification import MMSInstance, regenerate
from .mms_alternatives import MenuConfig, MenuAdapter, tool_definitions
from .records import RunLog, digest, json_text, read_events
from .reporting import _write
from .runner import provenance, run_episode
from .spending import pricing_for_model
from .verification_catalog import must_halt
from .verification_incremental_catalog import BatchBudget


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def seal(path):
    hashes = artifact_hashes(path)
    hashes.pop("integrity.json", None)
    _write(Path(path)/"integrity.json", json_text(hashes)+"\n")


def verify(path):
    hashes = artifact_hashes(path)
    hashes.pop("integrity.json", None)
    if hashes != load(Path(path)/"integrity.json"):
        raise ValueError("artifact integrity mismatch")


def prepare(catalog=CATALOG, output_root=RUNS):
    cases, comparisons, source = read_catalog(catalog)
    log = RunLog(output_root, "mms-menu-cpu")
    log.write_json("manifest.json", {"version": VERSION, "source_catalog": source,
        "cases": [{"case_id": c["id"], "hash": digest(c)} for c in cases],
        "tool_hashes": {m: digest(tool_definitions(MenuConfig(menu=m))) for m in ("original", "expanded")},
        "selection": "All six existing development studies in frozen order; no new case selection.",
        "future_live_slots": 12, "api_maximum_usd": "2.00", **provenance(ROOT)})
    log.write_json("private/studies.json", cases)
    log.write_json("cpu-comparisons.json", comparisons)
    rows = []
    try:
        for case in cases:
            for menu, cls in (("original", Audit), ("expanded", AlternativeAudit)):
                episode = RunLog(log.path/"episodes", menu)
                try:
                    env = cls(case, 10, sink=episode.event)
                    diagnostics = run_policy("study_aware", env.describe(), env.call)
                    result = {"case_id":case["id"], "menu":menu, "evaluation":score(env.submission,case),
                              "spent":env.status()["spent"], "diagnostics":diagnostics}
                    if result["evaluation"] != comparisons[case["id"]]["study_aware"]["evaluation"]:
                        raise ValueError("original CPU verdict changed")
                    episode.write_json("artifacts.json", env.artifacts())
                    episode.write_json("result.json", result)
                    rows.append(result)
                finally:
                    episode.close()
            diagnostics_log = RunLog(log.path/"diagnostics", case["id"])
            try:
                env = AlternativeAudit(case, 10, sink=diagnostics_log.event)
                results = []
                for n in (8,16,32):
                    results.append(env.call(f"affine-{n}", "run_affine_mms", family=case["family"], grid=n, kernel="audited"))
                results.append(env.call("iterative", "crosscheck_linear_solver", result_id="original"))
                coarse = env.call("coarse", "run_study", grid=8, kernel="audited")
                fine = env.call("fine", "run_study", grid=16, kernel="audited")
                results += [coarse, fine, env.call("extrapolate", "richardson", coarse_id=coarse["result"]["id"],
                                                  fine_id=fine["result"]["id"], assumed_order=2)]
                if any(not r["ok"] or r["result"].get("status") == "failed" for r in results):
                    raise ValueError("CPU alternative check failed")
                diagnostics_log.write_json("results.json", {"case_id":case["id"], "results":results})
                diagnostics_log.write_json("artifacts.json", env.artifacts())
            finally:
                diagnostics_log.close()
        log.write_json("summary.json", {"mode":"CPU commissioning", "rows":rows, "api_usd":0})
    finally:
        log.close()
    seal(log.path)
    print(log.path, flush=True)
    return log.path


def load_prepared(path):
    path = Path(path).resolve()
    verify(path)
    manifest = load(path/"manifest.json")
    current = provenance(ROOT)
    if manifest["version"] != VERSION or any(manifest[k] != current[k] for k in ("source_hashes", "dependencies")):
        raise ValueError("implementation changed since CPU preparation")
    cases = load(path/"private/studies.json")
    if manifest["cases"] != [{"case_id":c["id"], "hash":digest(c)} for c in cases] or len(cases) != 6:
        raise ValueError("prepared cases changed")
    return cases, load(path/"cpu-comparisons.json"), manifest


def slots_for(cases):
    return [{"case_id":c["id"], "study_hash":digest(c), "menu":menu} for i,c in enumerate(cases)
            for menu in (("original","expanded") if i % 2 == 0 else ("expanded","original"))]


def aggregate(rows):
    result = {}
    for menu in ("original", "expanded"):
        group = [r for r in rows if r["menu"] == menu]
        result[menu] = {"attempts":len(group), "complete":sum(r["evaluation"]["complete"] for r in group),
            "joint_correct":sum(r["evaluation"]["joint_correct"] for r in group),
            "qoi_correct":sum(r["evaluation"]["qoi"]["correct"] for r in group),
            "order_correct":sum(r["evaluation"]["order"]["correct"] for r in group),
            "mean_credits":statistics.mean(r["evaluation"]["scientific_status"]["spent"] for r in group) if group else None,
            "mean_seconds":statistics.mean(r["elapsed_seconds"] for r in group) if group else None,
            "extra_calls":sum(r["extra_calls"] for r in group),
            "api_upper_usd":str(sum((Decimal(r["api_budget"]["committed_upper_usd"]) for r in group),Decimal(0)))}
    return result


def render(path):
    path = Path(path).resolve()
    if (path/"integrity.json").exists():
        verify(path)
    manifest = load(path/"manifest.json")
    cases = {c["id"]:c for c in load(path/"private/studies.json")}
    rows = [load(p) for p in sorted((path/"results").glob("*.json"))]
    seen = set()
    for row in rows:
        slot = row["slot"]
        if slot in seen or any(row[k] != v for k,v in manifest["slots"][slot].items()):
            raise ValueError("duplicate or mismatched slot")
        seen.add(slot)
        e = row["evaluation"]
        expected = score(e["submission"], cases[row["case_id"]])
        if any(e[k] != v for k,v in expected.items()):
            raise ValueError("saved score mismatch")
        episode = Path(row["run"])
        if not episode.resolve().is_relative_to(path):
            raise ValueError("episode path leaves campaign")
        events, _ = read_events(episode)
        final = next((e for e in reversed(events) if e["kind"] == "run_finished"), None)
        if final is None or any(final[k] != row[k] for k in ("evaluation","api_budget","termination_reason")):
            raise ValueError("events/results mismatch")
        actions = [{"name":e["name"],"arguments":e["arguments"]} for e in events if e["kind"] == "tool_requested"]
        if row["actions"] != actions or row["extra_calls"] != sum(a["name"] in EXTRA_ACTIONS for a in actions):
            raise ValueError("tool action mismatch")
        regenerate(episode)  # Saved events only; no tool execution or API.
    summary = {"mode":manifest["mode"], "planned_slots":12, "finalized":len(rows),
               "menus":aggregate(rows), "rows":rows, "batch_budget":load(path/"batch-budget.json")}
    lines = ["# MMS original/expanded menu comparison", "",
        f"Mode: {manifest['mode']}; Luna/high; 10 scientific credits per episode; $2 total API ceiling.", "",
        "Six existing development studies on three physical systems, including an identical harmless control. "
        "Twelve fresh episodes, one per study/menu; no retries or changed claims.", ""]
    if manifest["mode"] == "dry-run":
        lines += ["SCRIPTED OFFLINE FIXTURES, not model performance. Actual API spending zero.", ""]
    lines += ["| Menu | Value correct | Order correct | Both correct | Complete | Mean credits | Extra calls | API upper USD |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for m,s in summary["menus"].items():
        mean = f"{s['mean_credits']:.4f}" if s["attempts"] else "n/a"
        lines.append(f"| {m} | {s['qoi_correct']}/6 | {s['order_correct']}/6 | {s['joint_correct']}/6 | {s['complete']}/6 | {mean} | {s['extra_calls']} | {s['api_upper_usd']} |")
    lines += ["", "| Study | Category | Menu | Value | Order | Both correct | Credits | Transcript |",
              "|---|---|---|---|---|---|---:|---|"]
    for r in rows:
        e = r["evaluation"]
        trace = (Path(r["run"])/"transcript.md").relative_to(path).as_posix()
        lines.append(f"| {r['case_id']} | {r['category']} | {r['menu']} | {e['qoi']['verdict']} | {e['order']['verdict']} | {e['joint_correct']} | {e['scientific_status']['spent']:.4f} | [trace]({trace}) |")
    lines += ["", "The unchanged study-aware CPU route gets both claims correct on all six cases in both menus, at 8.8166 credits. "
        "That route's numerical feasibility was an original commissioning requirement, not generalization evidence.", "",
        "Added tools are real numerical checks. An affine test need not reveal first-order error; algebraic agreement "
        "does not test discretization correctness; Richardson assumes its supplied order. The successful original route remains available.", "",
        "One sample per menu/case is descriptive; no semantic grading, validated confidence, or statistical superiority claim.", "",
        "## API accounting", "", "Conservative bounds, not an invoice; uncertain usage keeps its reservation.", "",
        "```json", json_text(summary["batch_budget"]), "```", ""]
    _write(path/"summary.json", json_text(summary)+"\n")
    _write(path/"report.md", "\n".join(lines))
    return summary


async def run_comparison(prepared, output_root=RUNS, *, mode):
    if mode not in ("live", "dry-run"):
        raise ValueError("explicit live/dry-run required")
    cases, comparisons, cpu = load_prepared(prepared)
    config, money, frozen = MenuConfig(), BatchBudget("2.00"), provenance(ROOT)
    log = RunLog(output_root, "mms-menu-"+mode)
    slots = slots_for(cases)
    log.write_json("manifest.json", {"version":VERSION, "mode":mode, "config":config.public(), "slots":slots,
        "prepared_path":str(Path(prepared).resolve()), "prepared_manifest_hash":digest(cpu),
        "api_maximum_usd":"2.00", "maximum_live_slots":12, "automatic_retries":False,
        "tool_hashes":cpu["tool_hashes"], "pricing":pricing_for_model(config.model),
        "pricing_reverified":"2026-09-12", "pricing_source":"https://developers.openai.com/api/docs/pricing", **frozen})
    log.write_json("private/studies.json", cases)
    log.write_json("cpu-comparisons.json", comparisons)
    log.write_json("batch-budget.json", money.status())
    log.event("campaign_started", mode=mode, slots=12)
    print(log.path, flush=True)
    try:
        for index,slot in enumerate(slots):
            current = provenance(ROOT)
            if any(current[k] != frozen[k] for k in ("source_hashes","dependencies")):
                raise ValueError("implementation changed during frozen campaign")
            minimum = Decimal(pricing_for_model(config.model)["output_per_million_usd"])*config.max_output_tokens/1_000_000
            allowance = money.reserve(index, minimum, "2.00")
            if allowance is None:
                log.event("campaign_halted", reason="batch_api_ceiling")
                break
            log.write_json("batch-budget.json", money.status(), replace=True)
            log.write_json(f"slots/{index:02d}.json", {**slot,"state":"attempted","allowance":str(allowance)})
            log.event("slot_started", slot=index, **slot)
            case = next(c for c in cases if c["id"] == slot["case_id"])
            instance = MMSInstance(case, comparisons[case["id"]], cpu["source_catalog"],
                                  {"campaign":str(log.path.resolve()), "slot":index, "ceiling_usd":"2.00"})
            episode, reason = await run_episode(ROOT, log.path/"episodes", mode=mode,
                config=replace(config, menu=slot["menu"], api_ceiling_usd=str(allowance)),
                instance=instance, adapter=MenuAdapter())
            result = load(episode/"evaluation.json")
            money.settle(index, result["api_budget"])
            events, _ = read_events(episode)
            actions = [{"name":e["name"], "arguments":e["arguments"]} for e in events if e["kind"] == "tool_requested"]
            row = {**slot, "slot":index, "category":case["category"], "run":str(episode.resolve()), **result,
                   "actions":actions, "extra_calls":sum(a["name"] in EXTRA_ACTIONS for a in actions)}
            log.write_json(f"results/{index:02d}.json", row)
            log.write_json("batch-budget.json", money.status(), replace=True)
            log.event("slot_finished", slot=index, result=row)
            render(log.path)
            e = result["evaluation"]
            print(f"{index+1}/12 {slot['menu']}: {reason}; both={e['joint_correct']}; "
                  f"credits={e['scientific_status']['spent']:.4f}; extra={row['extra_calls']}", flush=True)
            if reason == "api_ceiling" or must_halt(episode,reason):
                log.event("campaign_halted",reason=reason)
                break
        else:
            log.event("campaign_finished",slots=12)
        if provenance(ROOT)["source_hashes"] != frozen["source_hashes"]:
            raise ValueError("source changed before completion")
    finally:
        log.write_json("batch-budget.json", money.status(), replace=True)
        render(log.path)
        log.close()
        seal(log.path)
    return log.path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--cpu",action="store_true")
    mode.add_argument("--dry-run",action="store_true")
    mode.add_argument("--live",action="store_true")
    mode.add_argument("--render",type=Path)
    parser.add_argument("--prepared",type=Path)
    parser.add_argument("--catalog",type=Path,default=CATALOG)
    parser.add_argument("--output-root",type=Path,default=RUNS)
    args = parser.parse_args()
    if args.render:
        result = render(args.render)
        print(json_text({k:v for k,v in result.items() if k != "rows"}))
    elif args.cpu:
        prepare(args.catalog,args.output_root)
    else:
        if args.prepared is None:
            parser.error("--prepared CPU directory required")
        asyncio.run(run_comparison(args.prepared,args.output_root,mode="live" if args.live else "dry-run"))


if __name__ == "__main__":
    main()
