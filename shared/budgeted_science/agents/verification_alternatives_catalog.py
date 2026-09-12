"""Five frozen predator-prey cases; matched original/expanded Luna tool menus."""
import argparse
import asyncio
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import re
from time import monotonic

from ..claim_verification.alternatives import EXTRA_COSTS, VERSION
from ..claim_verification.fixed_baseline import fixed_two_check
from ..claim_verification.studies import CATEGORIES, SEEDS
from ..mms_verification.experiment import artifact_hashes
from .records import RunLog, digest, json_text, read_events
from .reporting import _write
from .runner import provenance, run_episode
from .spending import pricing_for_model
from .verification_cli import ROOT, CATALOG
from .verification_catalog import read_catalog, must_halt, result_row, summarize
from .verification_incremental_catalog import BatchBudget
from .verification_alternatives import (AlternativesAdapter, AlternativesConfig, AlternativesEpisode,
                                       AlternativesInstance, prompts, tool_definitions)

RUNS = ROOT / "demos/claim_verification/runs"


def select_cases(studies):
    """One category per system, in predefined order; never inspect outcomes."""
    selected = []
    for seed, category in zip(SEEDS, CATEGORIES):
        matches = [s for s in studies if s["private"]["seed"] == seed
                   and s["private"]["category"] == category]
        if len(matches) != 1:
            raise ValueError("predeclared seed/category case missing or duplicated")
        selected.append(deepcopy(matches[0]))
    return selected


def seal(path):
    hashes = artifact_hashes(path)
    hashes.pop("integrity.json", None)
    _write(Path(path)/"integrity.json", json_text(hashes)+"\n")


def check_integrity(path):
    path = Path(path)
    hashes = artifact_hashes(path)
    hashes.pop("integrity.json", None)
    if hashes != json.loads((path/"integrity.json").read_text(encoding="utf-8")):
        raise ValueError("saved experiment artifact integrity mismatch")


def single_check(call, name):
    inventory = call("list_artifacts", {})["artifacts"]
    analysis = next(a for a in inventory if a["role"] == "analysis")
    text = call("read_artifact", {"id": analysis["id"]})["content"]
    reported = float(re.findall(r"^Result:\s*(\S+)\s*$", text, re.MULTILINE)[0])
    result = call(name, {"run_id": analysis["run_id"]})
    verdict = "ABSTAIN"
    evidence = [analysis["id"]]
    if result["status"] == "success":
        verdict = "ACCEPT" if abs(reported-result["q"])/abs(result["q"]) <= .05 else "REJECT"
        evidence.append(result["run_id"])
    call("submit", {"verdict": verdict, "diagnosis": "Single-check diagnostic control.",
                    "evidence_ids": evidence,
                    "justification": "Comparison with one purchased calculation; not a certified bound."})
    return {"reported_q": reported, "check": result}


def cpu_episode(study, root, menu, policy="fixed_two_check"):
    log = RunLog(root, "menu-cpu")
    start = monotonic()
    try:
        config = AlternativesConfig(menu=menu)
        instance = AlternativesInstance(study)
        episode = AlternativesEpisode(config, instance, log, start+300)
        messages = prompts(config, episode)
        log.write_json("manifest.json", {"mode": "cpu", "menu": menu, "policy": policy,
                                        "case_id": study["case_id"], "config": config.public()})
        log.event("prompt_frozen", messages=messages)
        count = 0
        def call(name, args):
            nonlocal count
            count += 1
            if name == "read_artifact":
                args = {"offset": 0, "limit": 200, **args}
            output = episode.execute(f"cpu-{count}", name, json.dumps(args))
            return output.get("result", {"status": "invalid"})
        try:
            diagnostics = fixed_two_check(call) if policy == "fixed_two_check" else single_check(call, policy)
        except Exception as exc:
            episode.environment.abort("CPU diagnostic failed")
            diagnostics = {"error": log.redactor.error(exc)}
            log.event("cpu_error", **diagnostics)
        result = {"case_id": study["case_id"], "menu": menu, "policy": policy,
                  "evaluation": episode.evaluate(), "submission": episode.submission,
                  "diagnostics": diagnostics, "runtime_seconds": monotonic()-start,
                  "episode_path": str(log.path.resolve()), "api_usd": 0}
        log.write_json("result.json", result)
        log.event("cpu_finished", result=result)
    finally:
        log.close()
    render_cpu_episode(log.path)
    return result


def render_cpu_episode(path):
    path = Path(path)
    result = json.loads((path/"result.json").read_text(encoding="utf-8"))
    events, torn = read_events(path)
    if torn:
        raise ValueError("torn CPU log")
    lines = ["# CPU numerical audit trace", "", "No model or API calls.", ""]
    for event in events:
        if event["kind"] in ("prompt_frozen", "tool_requested", "tool_result", "simulation_finished"):
            lines += ["```json", json_text(event), "```", ""]
    lines += ["## Final result", "", "```json", json_text(result), "```", ""]
    _write(path/"transcript.md", "\n".join(lines))


def prepare(catalog=CATALOG, output_root=RUNS):
    all_studies, catalog_hash = read_catalog(catalog)
    studies = select_cases(all_studies)
    frozen = provenance(ROOT)
    log = RunLog(output_root, "prey-menu-cpu")
    try:
        cases = [{"case_id": s["case_id"], "study_hash": digest(s),
                  "seed": s["private"]["seed"], "category": s["private"]["category"]} for s in studies]
        log.write_json("manifest.json", {"version": VERSION, "mode": "cpu", "cases": cases,
            "catalog": str(Path(catalog).resolve()), "catalog_digest": catalog_hash,
            "selection": "category i at system seed 7100+i; fixed before new measurements",
            "scientific_budget": 5, "api_maximum_usd": "2.00", "extra_prices": EXTRA_COSTS,
            "tool_hashes": {m: digest(AlternativesAdapter.tool_definitions(AlternativesConfig(menu=m)))
                            for m in ("original", "expanded")}, **frozen})
        log.write_json("private/studies.json", studies)
        results = []
        for study in studies:
            for menu in ("original", "expanded"):
                results.append(cpu_episode(study, log.path/"episodes", menu))
            for action in EXTRA_COSTS:
                results.append(cpu_episode(study, log.path/"episodes", "expanded", action))
        log.write_json("cpu-results.json", results)
        log.event("cpu_completed", cases=5, policy_episodes=len(results))
        if provenance(ROOT)["source_hashes"] != frozen["source_hashes"]:
            raise ValueError("implementation changed during CPU evaluation")
    finally:
        log.close()
    render_cpu(log.path)
    seal(log.path)
    return log.path


def render_cpu(path):
    path = Path(path)
    if (path/"integrity.json").exists():
        check_integrity(path)
    rows = json.loads((path/"cpu-results.json").read_text(encoding="utf-8"))
    lines = ["# Predator-prey alternative tools: CPU checks", "",
             "Five development studies across five systems; 25 policy/check episodes, not 25 independent studies.",
             "Single-check policies are diagnostic controls, not strong complete verifiers. API expenditure: $0.", "",
             "| Menu | Policy | Correct | Mean credits |", "|---|---|---:|---:|"]
    groups = [(m, "fixed_two_check") for m in ("original", "expanded")]
    groups += [("expanded", p) for p in EXTRA_COSTS]
    for menu, policy in groups:
        group = [r for r in rows if r["menu"] == menu and r["policy"] == policy]
        lines.append(f"| {menu} | {policy} | {sum(r['evaluation']['correct'] for r in group)}/{len(group)} | "
                     f"{sum(r['evaluation']['spent'] for r in group)/len(group):g} |")
    lines += ["", "## Traces", ""]
    for row in rows:
        episode = Path(row["episode_path"])
        render_cpu_episode(episode)
        lines.append(f"- {row['case_id']}, {row['menu']}, {row['policy']}: "
                     f"[trace]({episode.relative_to(path).as_posix()}/transcript.md)")
    _write(path/"report.md", "\n".join(lines)+"\n")
    return {"cases": 5, "episodes": len(rows)}


def load_prepared(path, *, frozen=True):
    path = Path(path).resolve()
    check_integrity(path)
    manifest = json.loads((path/"manifest.json").read_text(encoding="utf-8"))
    studies = json.loads((path/"private/studies.json").read_text(encoding="utf-8"))
    rows = json.loads((path/"cpu-results.json").read_text(encoding="utf-8"))
    if manifest["version"] != VERSION or len(studies) != 5 or len(rows) != 25:
        raise ValueError("wrong prepared experiment")
    if [digest(s) for s in studies] != [c["study_hash"] for c in manifest["cases"]]:
        raise ValueError("prepared case mismatch")
    if frozen and provenance(ROOT)["source_hashes"] != manifest["source_hashes"]:
        raise ValueError("implementation changed after CPU freeze; prepare again before live evaluation")
    comparisons = {(r["case_id"], r["menu"]): r for r in rows if r["policy"] == "fixed_two_check"}
    if len(comparisons) != 10:
        raise ValueError("missing/duplicate paired CPU controls")
    return studies, comparisons, manifest


def render(path):
    path = Path(path).resolve()
    if (path/"integrity.json").exists():
        check_integrity(path)
    manifest = json.loads((path/"manifest.json").read_text(encoding="utf-8"))
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((path/"results").glob("*.json"))]
    cases = {s["case_id"]: s for s in json.loads((path/"private/studies.json").read_text(encoding="utf-8"))}
    slots = {r["slot"]: r for r in rows}
    if len(slots) != len(rows):
        raise ValueError("duplicate finalized slot")
    for row in rows:
        expected_slot = manifest["slots"][row["slot"]]
        if (row["case_id"], row["menu"]) != (expected_slot["case_id"], expected_slot["menu"]):
            raise ValueError("slot identity mismatch")
        episode = (path/row["run"]).resolve()
        if not episode.is_relative_to(path):
            raise ValueError("episode outside batch")
        events, torn = read_events(episode)
        final = next((e for e in reversed(events) if e["kind"] == "run_finished"), None)
        if torn or final is None:
            raise ValueError("missing complete episode log")
        saved = json.loads((episode/"evaluation.json").read_text(encoding="utf-8"))
        if final["evaluation"] != saved["evaluation"] or final["api_budget"] != saved["api_budget"]:
            raise ValueError("evaluation/event mismatch")
        derived = result_row(cases[row["case_id"]], episode, path, saved)
        if any(row[k] != v for k, v in derived.items()):
            raise ValueError("saved aggregate result mismatch")
        if row["claim_valid"] != cases[row["case_id"]]["private"]["claim_valid"]:
            raise ValueError("claim label mismatch")
    summary = {"mode": manifest["mode"], "planned_slots": 10, "attempted_finished": len(rows),
               "menus": {m: summarize([r for r in rows if r["menu"] == m]) for m in ("original", "expanded")},
               "batch_budget": json.loads((path/"batch-budget.json").read_text(encoding="utf-8")), "rows": rows}
    lines = ["# Predator-prey: original versus expanded tool menu", "",
             f"Mode: {manifest['mode']}; Luna/high; five credits per episode; $2 whole-batch API ceiling.",
             "Five existing development systems, one category per system. One fresh episode per menu/case, no automatic retries.", ""]
    if manifest["mode"] == "dry-run":
        lines += ["Scripted fake responses, not model performance. Actual API expenditure is zero.", ""]
    lines += ["| Menu | Correct | Finished attempts | Mean credits | Extra-tool calls | API upper USD |",
              "|---|---:|---:|---:|---:|---:|"]
    for menu, s in summary["menus"].items():
        extra = sum(r["extra_tool_calls"] for r in rows if r["menu"] == menu)
        mean = f"{s['mean_audit_credits']:.3f}" if s["attempts"] else "n/a"
        lines.append(f"| {menu} | {s['correct']} | {s['attempts']}/5 | {mean} | {extra} | {s['api_committed_upper_usd']} |")
    lines += ["", "## Cases", "", "| Case | Category | Menu | Verdict | Correct | Credits | Trace |",
              "|---|---|---|---|---|---:|---|"]
    for row in rows:
        lines.append(f"| {row['case_id']} | {row['category']} | {row['menu']} | {row['verdict']} | "
                     f"{row['correct']} | {row['spent']:g} | [transcript]({row['run']}/transcript.md) |")
    lines += ["", "Added tools are real numerical calculations, not broken tools. The original successful two-check route remains affordable.",
              "Differences from one run per condition are descriptive, not a reliable causal estimate. Explanations are not semantically scored.",
              "", "## Batch accounting", "", "```json", json_text(summary["batch_budget"]), "```", ""]
    _write(path/"summary.json", json_text(summary)+"\n")
    _write(path/"report.md", "\n".join(lines))
    return summary


async def run_comparison(prepared, output_root=RUNS, *, mode):
    if mode not in ("dry-run", "live"):
        raise ValueError("explicit live or dry-run mode required")
    studies, comparisons, cpu_manifest = load_prepared(prepared)
    config, money, frozen = AlternativesConfig(), BatchBudget("2.00"), provenance(ROOT)
    log = RunLog(output_root, "prey-menu-"+mode)
    slots = [{"case_id": s["case_id"], "menu": menu} for i, s in enumerate(studies)
             for menu in (("original", "expanded") if i % 2 == 0 else ("expanded", "original"))]
    log.write_json("manifest.json", {"version": VERSION, "mode": mode, "config": config.public(), "slots": slots,
        "prepared_path": str(Path(prepared).resolve()), "prepared_manifest_hash": digest(cpu_manifest),
        "api_maximum_usd": "2.00", "maximum_live_slots": 10, "automatic_retries": False,
        "pricing": pricing_for_model(config.model), "pricing_reverified": "2026-09-12",
        "pricing_source": "https://developers.openai.com/api/docs/pricing", **frozen})
    log.write_json("private/studies.json", studies)
    log.write_json("cpu-comparisons.json", list(comparisons.values()))
    log.write_json("batch-budget.json", money.status())
    log.event("campaign_started", mode=mode, cases=5, slots=10)
    print(log.path, flush=True)
    try:
        for index, slot in enumerate(slots):
            current = provenance(ROOT)
            if current["source_hashes"] != frozen["source_hashes"] or current["dependencies"] != frozen["dependencies"]:
                raise ValueError("implementation changed during frozen campaign")
            minimum = Decimal(pricing_for_model(config.model)["output_per_million_usd"])*config.max_output_tokens/1_000_000
            allowance = money.reserve(index, minimum, "2.00")
            if allowance is None:
                log.event("campaign_halted", reason="batch_api_ceiling")
                break
            log.write_json("batch-budget.json", money.status(), replace=True)
            log.write_json(f"slots/{index:02d}.json", {**slot, "state": "attempted", "allowance": str(allowance)})
            log.event("slot_started", slot=index, **slot)
            study = next(s for s in studies if s["case_id"] == slot["case_id"])
            instance = AlternativesInstance(study, cpu_manifest["catalog"], cpu_manifest["catalog_digest"],
                cpu_manifest["selection"], comparisons[(study["case_id"], slot["menu"])],
                {"campaign": str(log.path.resolve()), "slot": index, "ceiling_usd": "2.00"})
            episode, reason = await run_episode(ROOT, log.path/"episodes", mode=mode,
                config=replace(config, menu=slot["menu"], api_ceiling_usd=str(allowance)),
                instance=instance, adapter=AlternativesAdapter())
            result = json.loads((episode/"evaluation.json").read_text(encoding="utf-8"))
            money.settle(index, result["api_budget"])
            events, _ = read_events(episode)
            actions = [e for e in events if e["kind"] == "tool_requested"]
            row = {**result_row(study, episode, log.path, result), "slot": index, "menu": slot["menu"],
                   "extra_tool_calls": sum(e["name"] in EXTRA_COSTS for e in actions),
                   "actions": [{"name": e["name"], "arguments": e["arguments"]} for e in actions]}
            log.write_json(f"results/{index:02d}.json", row)
            log.write_json("batch-budget.json", money.status(), replace=True)
            log.event("slot_finished", slot=index, result=row)
            render(log.path)
            print(f"{index+1}/10 {slot['menu']}: {reason}; correct={row['correct']}; "
                  f"credits={row['spent']:g}; extra calls={row['extra_tool_calls']}; API upper={row['api_upper_usd']}", flush=True)
            if reason == "api_ceiling" or must_halt(episode, reason):
                log.event("campaign_halted", reason=reason)
                break
        else:
            log.event("campaign_finished", slots=10)
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
    mode.add_argument("--cpu", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--render", type=Path)
    parser.add_argument("--prepared", type=Path)
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--output-root", type=Path, default=RUNS)
    args = parser.parse_args()
    if args.render:
        summary = render(args.render) if (args.render/"batch-budget.json").exists() else render_cpu(args.render)
        print(json_text({k: v for k, v in summary.items() if k != "rows"}))
    elif args.cpu:
        print(prepare(args.catalog, args.output_root))
    else:
        if args.prepared is None:
            parser.error("--prepared CPU directory is required for an agent comparison")
        asyncio.run(run_comparison(args.prepared, args.output_root, mode="live" if args.live else "dry-run"))


if __name__ == "__main__":
    main()
