"""One Luna/high episode per saved transport claim, with a $2 whole-batch cap."""

import argparse
import asyncio
from dataclasses import replace
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path

from ..transport_verification import VERSION
from ..transport_verification.environment import Episode
from ..transport_verification.experiment import POLICIES
from .records import RunLog, digest, json_text, read_events
from .runner import provenance, run_episode
from .spending import pricing_for_model
from .transport_verification import (TransportAdapter, TransportConfig, TransportInstance,
                                     regenerate, tool_definitions)
from .verification_catalog import summarize, must_halt
from .verification_incremental_catalog import BatchBudget

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT/"demos/claim_verification/runs/20260912T054409Z-transport-cpu-b5aefbda0e"
OUTPUT = ROOT/"demos/claim_verification/runs"


def read_catalog(path):
    path = Path(path).resolve()
    manifest = json.loads((path/"manifest.json").read_text(encoding="utf-8"))
    studies = json.loads((path/"catalog.json").read_text(encoding="utf-8"))
    if manifest["version"] != VERSION or manifest["budget"] != 4 or digest(studies) != manifest["catalog_hash"]:
        raise ValueError("frozen transport catalog mismatch")
    for relative, expected in manifest["source_hashes"].items():
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest() != expected:
            raise ValueError("scientific source changed since CPU evaluation: "+relative)
    ids = [s["id"] for s in studies]
    if len(ids) != 12 or len(set(ids)) != 12 or ids != manifest["case_ids"]:
        raise ValueError("expected twelve frozen cases in saved order")
    expected_evaluations = {s["id"]: Episode(s).evaluation() for s in studies}
    comparisons = {case: {} for case in ids}
    files = [path/"manifest.json", path/"catalog.json"]
    events, torn = read_events(path)
    if torn or not any(e["kind"] == "campaign_finished" for e in events):
        raise ValueError("CPU campaign incomplete")
    for event in events:
        if event["kind"] != "episode_completed":
            continue
        file = (path/event["path"]/"result.json").resolve()
        if not file.is_relative_to(path):
            raise ValueError("CPU result path escapes catalog")
        row = json.loads(file.read_text(encoding="utf-8"))
        case, policy = row["case_id"], row["policy"]
        if case not in comparisons or policy not in POLICIES or policy in comparisons[case]:
            raise ValueError("unexpected or repeated CPU comparison")
        e, expected = row["evaluation"], expected_evaluations[case]
        if (e["valid"] != expected["valid"] or e["reference"] != expected["reference"]
                or e["original_relative_error"] != expected["original_relative_error"]
                or e["incomplete"] or not 0 <= e["spent"] <= 4
                or e["correct"] != (e["verdict"] == ("ACCEPT" if e["valid"] else "REJECT"))):
            raise ValueError("CPU evaluation does not match original claim")
        comparisons[case][policy] = row
        files.append(file)
    if any(set(c) != set(POLICIES) for c in comparisons.values()):
        raise ValueError("missing saved CPU comparison")
    return studies, comparisons, {"path": str(path), "catalog_digest": digest(studies),
        "file_hashes": {f.relative_to(path).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}


def row_for(study, path, campaign, result):
    e, money = result["evaluation"], result["api_budget"]
    usage = money["measured_responses"]
    return {"case_id": study["id"], "quantity": study["public"]["claim"]["quantity"],
        "run": Path(os.path.relpath(path, campaign)).as_posix(), "termination_reason": result["termination_reason"],
        "claim_valid": e["valid"], "verdict": e["verdict"], "correct": e["correct"],
        "covered": e["coverage"], "abstained": e["abstention"], "incomplete": e["incomplete"],
        "false_accept": e["verdict"] == "ACCEPT" and not e["valid"],
        "false_reject": e["verdict"] == "REJECT" and e["valid"], "spent": e["spent"],
        "elapsed_seconds": result["elapsed_seconds"], "model_responses": result["model_responses"],
        "api_upper_usd": money["committed_upper_usd"],
        "api_lower_usd": str(sum((Decimal(v["standard_cost_lower_usd"]) for v in usage), Decimal(0))),
        "uncertain_reserved_usd": money["uncertain_reserved_usd"],
        "input_tokens": sum(v["usage"]["input_tokens"] for v in usage),
        "output_tokens": sum(v["usage"]["output_tokens"] for v in usage),
        "reasoning_tokens": sum(v["usage"].get("output_tokens_details", {}).get("reasoning_tokens", 0) for v in usage),
        "baseline_correct": bool((result.get("fixed_policy") or {}).get("evaluation", {}).get("correct", False))}


def render(path):
    path = Path(path)
    manifest = json.loads((path/"manifest.json").read_text(encoding="utf-8"))
    rows = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((path/"results").glob("*.json"))]
    slots = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((path/"slots").glob("*.json"))]
    if len({r["case_id"] for r in rows}) != len(rows) or len({s["case_id"] for s in slots}) != len(slots):
        raise ValueError("duplicate campaign result or attempted slot")
    comparisons = json.loads((path/"cpu-comparisons.json").read_text(encoding="utf-8"))
    summary = {"mode": manifest["mode"], "planned": len(manifest["cases"]), "attempted": len(slots),
               "unfinalized_attempts": len(slots)-len(rows), "unattempted": len(manifest["cases"])-len(slots),
               "overall": summarize(rows), "by_quantity": {}, "cpu_comparisons": {},
               "batch_budget": json.loads((path/"batch-budget.json").read_text(encoding="utf-8"))}
    summary["incomplete_including_unfinalized"] = summary["overall"]["incomplete"]+summary["unfinalized_attempts"]
    for q in ("peak", "arrival", "exposure", "crossing"):
        summary["by_quantity"][q] = summarize([r for r in rows if r["quantity"] == q])
    for p in POLICIES:
        ev = [values[p]["evaluation"] for values in comparisons.values()]
        summary["cpu_comparisons"][p] = {"correct": sum(e["correct"] for e in ev), "count": len(ev)}
    total = summary["overall"]
    lines = ["# Luna transport-verification evaluation", "",
        f"Mode: {manifest['mode']}; model: gpt-5.6-luna; high reasoning; four audit credits per case.",
        f"Correct: {total['correct']}/{len(slots)} attempted; {summary['unattempted']} unattempted of twelve planned.",
        "Twelve development claims share three physical systems. No full-budget requirement, savings bonus or semantic explanation grading.",
        "API cap is $2 for the ENTIRE batch, not per case. Incomplete attempts and abstentions are nonsuccesses.", ""]
    if manifest["mode"] == "dry-run":
        lines += ["Scripted offline fixtures, NOT model performance. Actual API expenditure is zero; reported ledger usage is synthetic.", ""]
    lines += ["## Summary", "", "```json", json_text(summary), "```", "",
              "## Matched episodes", "", "| Case | Quantity | Valid claim | Verdict | Correct | Credits | Transcript |",
              "|---|---|---|---|---|---:|---|"]
    for r in rows:
        lines.append(f"| {r['case_id']} | {r['quantity']} | {r['claim_valid']} | {r['verdict']} | {r['correct']} | {r['spent']:.6g} | [Read]({r['run']}/transcript.md) |")
    lines += ["", "Saved CPU results were imported, not rerun, and were never given to Luna.",
              "No labels, reference values, case-generation strata or baseline recommendations enter the prompt.",
              "Physical coefficients and original configuration ARE public, as in the frozen CPU task.",
              "Costs are bounds, not invoices. API-visible material is logged; raw internal reasoning is unavailable.", ""]
    (path/"summary.json").write_text(json_text(summary)+"\n", encoding="utf-8")
    (path/"report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


async def run_catalog(catalog_path=CATALOG, output_root=OUTPUT, *, mode, gateway_factory=None):
    if mode not in ("dry-run", "live") or (mode == "live" and gateway_factory is not None):
        raise ValueError("invalid mode or live gateway override")
    studies, comparisons, source = read_catalog(catalog_path)
    config = TransportConfig()
    money = BatchBudget("2.00")
    frozen = provenance(ROOT)
    log = RunLog(output_root, "luna-transport-"+mode)
    cases = [{"case_id": s["id"], "study_hash": digest(s), "quantity": s["public"]["claim"]["quantity"]} for s in studies]
    minimum = Decimal(pricing_for_model(config.model)["output_per_million_usd"])*config.max_output_tokens/Decimal(1000000)
    log.write_json("manifest.json", {"mode": mode, "config": config.public(), "cases": cases,
        "source_catalog": source, "api_maximum_usd": "2.00", "max_live_slots": 12,
        "pricing": pricing_for_model(config.model), "pricing_reverified": "2026-09-12",
        "pricing_source": "https://developers.openai.com/api/docs/models/gpt-5.6-luna",
        "tool_schema_hash": digest(tool_definitions(config)), "automatic_retries": False,
        "order": "all twelve saved development claims, unchanged order", **frozen})
    log.write_json("cpu-comparisons.json", comparisons)
    log.write_json("batch-budget.json", money.status())
    print(log.path, flush=True)
    log.event("campaign_started", mode=mode, cases=12)
    try:
        for index, study in enumerate(studies):
            current = provenance(ROOT)
            if current["source_hashes"] != frozen["source_hashes"] or current["dependencies"] != frozen["dependencies"]:
                raise ValueError("implementation changed during frozen campaign")
            if digest(study) != cases[index]["study_hash"]:
                raise ValueError("frozen study changed")
            allowance = money.reserve(index, minimum, config.api_ceiling_usd)
            if allowance is None:
                log.event("campaign_halted", reason="batch_api_ceiling", index=index)
                break
            episode_config = replace(config, api_ceiling_usd=str(allowance))
            log.write_json("batch-budget.json", money.status(), replace=True)
            log.write_json(f"slots/{index:02d}.json", {"case_id": study["id"], "status": "attempted", "api_ceiling_usd": str(allowance)})
            log.event("case_started", index=index, case_id=study["id"], batch_budget=money.status())
            instance = TransportInstance(study, comparisons[study["id"]], source,
                                         {"campaign": str(log.path.resolve()), "slot": index, "ceiling_usd": "2.00"})
            path, reason = await run_episode(ROOT, output_root, mode=mode, config=episode_config,
                instance=instance, adapter=TransportAdapter(), gateway=gateway_factory(index) if gateway_factory else None)
            result = json.loads((path/"evaluation.json").read_text(encoding="utf-8"))
            row = row_for(study, path, log.path, result)
            money.settle(index, result["api_budget"])
            log.write_json(f"results/{index:02d}.json", row)
            log.write_json("batch-budget.json", money.status(), replace=True)
            log.event("case_finished", index=index, case_id=study["id"], result=row)
            summary = render(log.path)
            if Decimal(summary["overall"]["api_committed_upper_usd"]) > Decimal("2.00"):
                raise ValueError("batch spending exceeded ceiling")
            print(f"{index+1}/12 {study['id']}: {reason}; verdict={row['verdict']}; correct={row['correct']}; "
                  f"credits={row['spent']:g}; API upper={row['api_upper_usd']}", flush=True)
            if reason == "api_ceiling" or must_halt(path, reason):
                log.event("campaign_halted", reason=reason, case_id=study["id"])
                break
        else:
            log.event("campaign_finished", cases=12)
    finally:
        log.write_json("batch-budget.json", money.status(), replace=True)
        render(log.path)
        log.close()
    return log.path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--live", action="store_true")
    modes.add_argument("--render", type=Path)
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--output-root", type=Path, default=OUTPUT)
    args = parser.parse_args()
    if args.render:
        if (args.render/"cpu-comparisons.json").exists():
            print(json_text(render(args.render)))
        else:
            print(regenerate(args.render))
    else:
        asyncio.run(run_catalog(args.catalog, args.output_root, mode="live" if args.live else "dry-run"))


if __name__ == "__main__":
    main()
