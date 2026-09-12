"""Exactly one Luna/high episode per frozen study; $2 TOTAL batch ceiling."""
import argparse
import asyncio
from dataclasses import replace
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from ..study_verification import VERSION
from ..study_verification.environment import Episode
from ..study_verification.experiment import ROOT, RUNS, POLICIES
from .records import RunLog, digest, json_text, read_events
from .runner import provenance, run_episode
from .spending import pricing_for_model
from .study_verification import StudyAdapter, StudyConfig, StudyInstance, regenerate, tool_definitions
from .transport_catalog import row_for
from .verification_catalog import summarize, must_halt
from .verification_incremental_catalog import BatchBudget


def read_catalog(path):
    path = Path(path).resolve()
    manifest = json.loads((path/"manifest.json").read_text(encoding="utf-8"))
    studies = json.loads((path/"catalog.json").read_text(encoding="utf-8"))
    if manifest["version"] != VERSION or manifest["budget"] != 4 or digest(studies) != manifest["catalog_hash"]:
        raise ValueError("frozen scientific catalog mismatch")
    for relative, expected in manifest["scientific_source_hashes"].items():
        file = (ROOT/relative).resolve()
        if not file.is_relative_to(ROOT) or hashlib.sha256(file.read_bytes()).hexdigest() != expected:
            raise ValueError("scientific source changed after CPU pilot")
    ids = [s["id"] for s in studies]
    if len(ids) != 12 or len(set(ids)) != 12 or ids != manifest["case_ids"]:
        raise ValueError("expected twelve frozen unique studies")
    events, torn = read_events(path)
    if torn or not any(e["kind"] == "campaign_finished" for e in events):
        raise ValueError("CPU pilot incomplete")
    comparisons = {i: {} for i in ids}
    expected = {s["id"]: Episode(s).evaluation() for s in studies}
    files = [path/"manifest.json", path/"catalog.json"]
    for event in events:
        if event["kind"] != "episode_completed":
            continue
        file = (path/event["path"]/"result.json").resolve()
        if not file.is_relative_to(path):
            raise ValueError("result outside catalog")
        row = json.loads(file.read_text(encoding="utf-8"))
        case, p, e = row["case_id"], row["policy"], row["evaluation"]
        if case not in comparisons or p not in POLICIES or p in comparisons[case]:
            raise ValueError("unknown or duplicate CPU comparison")
        if (any(e[k] != expected[case][k] for k in ("valid", "reference", "original_relative_error")) or
                e["incomplete"] or not 0 <= e["spent"] <= 4 or
                e["correct"] != (e["verdict"] == ("ACCEPT" if e["valid"] else "REJECT"))):
            raise ValueError("CPU result/claim mismatch")
        comparisons[case][p] = row
        files.append(file)
    if any(set(v) != set(POLICIES) for v in comparisons.values()):
        raise ValueError("missing CPU comparison")
    return studies, comparisons, {"path": str(path), "catalog_digest": digest(studies),
        "file_hashes": {f.relative_to(path).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}


def render(path):
    path = Path(path)
    manifest = json.loads((path/"manifest.json").read_text(encoding="utf-8"))
    rows = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((path/"results").glob("*.json"))]
    slots = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((path/"slots").glob("*.json"))]
    if len({r["case_id"] for r in rows}) != len(rows) or len({s["case_id"] for s in slots}) != len(slots):
        raise ValueError("duplicate result or live slot")
    comparisons = json.loads((path/"cpu-comparisons.json").read_text(encoding="utf-8"))
    summary = {"mode": manifest["mode"], "planned": len(manifest["cases"]), "attempted": len(slots),
        "unfinalized_attempts": len(slots)-len(rows), "unattempted": len(manifest["cases"])-len(slots),
        "overall": summarize(rows), "cpu_comparisons": {},
        "batch_budget": json.loads((path/"batch-budget.json").read_text(encoding="utf-8"))}
    summary["incomplete_including_unfinalized"] = summary["overall"]["incomplete"]+summary["unfinalized_attempts"]
    for p in POLICIES:
        ev = [v[p]["evaluation"] for v in comparisons.values()]
        summary["cpu_comparisons"][p] = {"correct": sum(e["correct"] for e in ev), "count": len(ev)}
    lines = ["# Luna computational-study verification", "",
        f"Mode: {manifest['mode']}; GPT-5.6 Luna/high; four scientific credits; $2 entire-batch API cap.",
        f"Correct: {summary['overall']['correct']}/{len(slots)} attempted; {summary['unattempted']} unattempted.",
        "Twelve development claims share TWO systems. Numerical correctness only; no semantic diagnosis/confidence grading.", ""]
    if manifest["mode"] == "dry-run":
        lines += ["SCRIPTED fixtures, NOT model performance. Actual API expenditure: zero; ledger usage synthetic.", ""]
    lines += ["```json", json_text(summary), "```", "", "| Case | Family (private) | Valid | Verdict | Correct | Credits | Transcript |",
              "|---|---|---|---|---|---:|---|"]
    for r in rows:
        lines.append(f"| {r['case_id']} | {r['family']} | {r['claim_valid']} | {r['verdict']} | {r['correct']} | {r['spent']:.6f} | [Read]({r['run']}/transcript.md) |")
    lines += ["", "CPU outcomes, labels and references were withheld from model context. Approximate numerical tools and analytic shortcuts remain available in principle.",
              "API costs are bounds, not invoices. All available API-visible records retained; raw internal reasoning unavailable.", ""]
    (path/"summary.json").write_text(json_text(summary)+"\n", encoding="utf-8")
    (path/"report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


async def run_catalog(catalog_path, output_root=RUNS, *, mode, gateway_factory=None):
    if mode not in ("dry-run", "live") or (mode == "live" and gateway_factory is not None):
        raise ValueError("invalid mode or live gateway override")
    studies, comparisons, source = read_catalog(catalog_path)
    config, money, frozen = StudyConfig(), BatchBudget("2.00"), provenance(ROOT)
    log = RunLog(output_root, "luna-study-"+mode)
    cases = [{"case_id": s["id"], "study_hash": digest(s)} for s in studies]
    minimum = Decimal(pricing_for_model(config.model)["output_per_million_usd"])*config.max_output_tokens/Decimal(1000000)
    log.write_json("manifest.json", {"mode": mode, "config": config.public(), "cases": cases,
        "source_catalog": source, "api_maximum_usd": "2.00", "max_live_slots": 12,
        "pricing": pricing_for_model(config.model), "pricing_reverified": "2026-09-12",
        "pricing_source": "https://developers.openai.com/api/docs/pricing",
        "tool_schema_hash": digest(tool_definitions()), "automatic_retries": False, **frozen})
    log.write_json("cpu-comparisons.json", comparisons)
    log.write_json("batch-budget.json", money.status())
    print(log.path, flush=True)
    log.event("campaign_started", mode=mode, cases=12)
    try:
        for index, study in enumerate(studies):
            current = provenance(ROOT)
            if current["source_hashes"] != frozen["source_hashes"] or current["dependencies"] != frozen["dependencies"] or digest(study) != cases[index]["study_hash"]:
                raise ValueError("implementation or instance changed during frozen campaign")
            allowance = money.reserve(index, minimum, config.api_ceiling_usd)
            if allowance is None:
                log.event("campaign_halted", reason="batch_api_ceiling", index=index)
                break
            log.write_json("batch-budget.json", money.status(), replace=True)
            log.write_json(f"slots/{index:02d}.json", {"case_id": study["id"], "status": "attempted", "api_ceiling_usd": str(allowance)})
            log.event("case_started", index=index, case_id=study["id"])
            instance = StudyInstance(study, comparisons[study["id"]], source,
                                    {"campaign": str(log.path.resolve()), "slot": index, "ceiling_usd": "2.00"})
            path, reason = await run_episode(ROOT, output_root, mode=mode,
                config=replace(config, api_ceiling_usd=str(allowance)), instance=instance, adapter=StudyAdapter(),
                gateway=gateway_factory(index) if gateway_factory else None)
            result = json.loads((path/"evaluation.json").read_text(encoding="utf-8"))
            row = row_for(study, path, log.path, result)
            row["family"] = study["private_selection"]["family"]
            money.settle(index, result["api_budget"])
            log.write_json(f"results/{index:02d}.json", row)
            log.write_json("batch-budget.json", money.status(), replace=True)
            log.event("case_finished", index=index, result=row)
            render(log.path)
            print(f"{index+1}/12 {row['family']}: {reason}; verdict={row['verdict']}; correct={row['correct']}; credits={row['spent']:g}; API upper={row['api_upper_usd']}", flush=True)
            if reason == "api_ceiling" or must_halt(path, reason):
                log.event("campaign_halted", reason=reason)
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
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--output-root", type=Path, default=RUNS)
    args = parser.parse_args()
    if args.render:
        print(json_text(render(args.render)) if (args.render/"cpu-comparisons.json").exists() else regenerate(args.render))
    else:
        if args.catalog is None:
            parser.error("--catalog required: an explicitly selected frozen CPU pilot")
        asyncio.run(run_catalog(args.catalog, args.output_root, mode="live" if args.live else "dry-run"))


if __name__ == "__main__":
    main()
