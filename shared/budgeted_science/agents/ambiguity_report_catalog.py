"""Four report-style Luna/high runs, paired with saved scaffolded runs; $2 total."""
import argparse
import asyncio
from dataclasses import replace
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from . import ambiguity_agent as base
from .ambiguity_report import CONDITION, ReportConfig, ReportAdapter, regenerate, tool_definitions
from .records import RunLog, digest, json_text
from .runner import provenance, run_episode
from .spending import pricing_for_model
from .transport_verification import TransportInstance
from .verification_catalog import must_halt
from .verification_incremental_catalog import BatchBudget

science = base.science


def read_scaffolded(path, cases):
    path = Path(path).resolve()
    manifest = json.loads((path/"manifest.json").read_text(encoding="utf-8"))
    if manifest["mode"] != "live" or manifest["config"]["model"] != "gpt-5.6-luna" or manifest["config"]["reasoning_effort"] != "high":
        raise ValueError("expected saved Luna/high live comparison")
    files = [path/"manifest.json"]
    results = {}
    expected = {(c["id"], b): digest(c) for c in cases for b in science.BUDGETS}
    for f in sorted((path/"results").glob("*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        key = (r["case_id"], r["budget"])
        if key in results or key not in expected or r["study_hash"] != expected[key]:
            raise ValueError("scaffolded comparison case mismatch")
        cfg = json.loads((Path(r["run"])/"manifest.json").read_text(encoding="utf-8"))["public_configuration"]
        if (cfg["model"] != "gpt-5.6-luna" or cfg["reasoning_effort"] != "high"
                or cfg["scientific_budget"] != key[1] or cfg["task_variant"] != "forecast_ambiguity"
                or r["termination_reason"] != "submitted"):
            raise ValueError("scaffolded episode contract mismatch")
        results[key] = r
        files.extend([f, Path(r["run"])/"manifest.json", Path(r["run"])/"prompts.json", Path(r["run"])/"tools.json", Path(r["run"])/"evaluation.json"])
    if set(results) != set(expected):
        raise ValueError("expected all four saved scaffolded episodes")
    return {f"{c}:{b}":r for (c,b),r in results.items()}, {"path": str(path), "file_hashes": {
        str(f): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}


def render(path):
    path = Path(path)
    summary = base.render(path)
    before = json.loads((path/"scaffolded-comparisons.json").read_text(encoding="utf-8"))
    summary["condition"] = CONDITION
    summary["scaffolded_correct"] = sum(r["evaluation"]["correct"] for r in before.values())
    summary["scaffolded_abstained"] = sum(r["evaluation"]["abstained"] for r in before.values())
    report = (path/"report.md").read_text(encoding="utf-8").replace(
        "# Luna: finite-grid forecast-support audit", "# Luna: report-style audit with reduced strategy guidance", 1)
    report += "\nPrimary outcome is verdict correctness; evidence-backed correctness is a secondary procedural diagnostic, not a universal reasoning score.\n"
    report += "\n## Saved scaffolded comparison\n\nThis changes task wording, report presentation, tool descriptions and the submission schema together; it is not a pure single-sentence prompt ablation. No historical episode was rerun.\n\n"
    report += "| Evidence | Budget | Earlier verdict | New verdict | Earlier credits | New credits |\n|---|---:|---|---|---:|---:|\n"
    for r in summary["rows"]:
        old = before[f"{r['case_id']}:{r['budget']}"]
        report += f"| {r['regime']} | {r['budget']} | {old['evaluation']['verdict']} | {r['evaluation']['verdict']} | {old['evaluation']['credits_spent']:.6f} | {r['evaluation']['credits_spent']:.6f} |\n"
    report += "\nEach condition has one run per case/budget. Differences may reflect model sampling, presentation or guidance; this tiny exploratory comparison cannot isolate their effects.\n"
    (path/"summary.json").write_text(json_text(summary)+"\n", encoding="utf-8")
    (path/"report.md").write_text(report, encoding="utf-8")
    return summary


async def run_catalog(catalog_path, scaffolded_path, output_root=science.RUNS, *, mode, gateway_factory=None):
    if mode not in ("dry-run", "live") or (mode == "live" and gateway_factory is not None):
        raise ValueError("invalid mode or live gateway override")
    cases, comparisons, source = base.read_catalog(catalog_path)
    earlier, earlier_source = read_scaffolded(scaffolded_path, cases)
    config, money, frozen = ReportConfig(), BatchBudget("2.00"), provenance(science.ROOT)
    log = RunLog(output_root, "luna-report-"+mode)
    slots = [{"case_id": c["id"], "budget": b, "study_hash": digest(c)} for c in cases for b in science.BUDGETS]
    minimum = Decimal(pricing_for_model(config.model)["output_per_million_usd"])*config.max_output_tokens/Decimal(1000000)
    log.write_json("manifest.json", {"mode": mode, "condition": CONDITION, "config": config.public(), "cases": slots,
        "source_catalog": source, "scaffolded_source": earlier_source, "api_maximum_usd": "2.00", "max_live_slots": 4,
        "pricing": pricing_for_model(config.model), "pricing_reverified": "2026-09-12",
        "pricing_source": "https://developers.openai.com/api/docs/models/gpt-5.6-luna",
        "tool_schema_hash": digest(tool_definitions()), "automatic_retries": False, **frozen})
    log.write_json("cpu-comparisons.json", comparisons)
    log.write_json("scaffolded-comparisons.json", earlier)
    log.write_json("batch-budget.json", money.status())
    print(log.path, flush=True)
    log.event("campaign_started", mode=mode, cases=4)
    try:
        for index, slot in enumerate(slots):
            current = provenance(science.ROOT)
            if current["source_hashes"] != frozen["source_hashes"] or current["dependencies"] != frozen["dependencies"]:
                raise ValueError("implementation changed during frozen campaign")
            study = next(c for c in cases if c["id"] == slot["case_id"])
            if digest(study) != slot["study_hash"]:
                raise ValueError("instance changed during campaign")
            allowance = money.reserve(index, minimum, config.api_ceiling_usd)
            if allowance is None:
                log.event("campaign_halted", reason="batch_api_ceiling", index=index)
                break
            log.write_json("batch-budget.json", money.status(), replace=True)
            log.write_json(f"slots/{index:02d}.json", {**slot, "status": "attempted", "api_ceiling_usd": str(allowance)})
            log.event("case_started", index=index, **slot)
            instance = TransportInstance(study, comparisons[f"{slot['case_id']}:{slot['budget']}"], source,
                {"campaign": str(log.path.resolve()), "slot": index, "ceiling_usd": "2.00", "condition": CONDITION})
            path, reason = await run_episode(science.ROOT, output_root, mode=mode,
                config=replace(config, scientific_budget=slot["budget"], api_ceiling_usd=str(allowance)),
                instance=instance, adapter=ReportAdapter(), gateway=gateway_factory(index) if gateway_factory else None)
            result = json.loads((path/"evaluation.json").read_text(encoding="utf-8"))
            money.settle(index, result["api_budget"])
            row = {**slot, "regime": study["private"]["regime"], "run": str(path.resolve()), **result}
            log.write_json(f"results/{index:02d}.json", row)
            log.write_json("batch-budget.json", money.status(), replace=True)
            log.event("case_finished", index=index, result=row)
            render(log.path)
            e = result["evaluation"]
            print(f"{index+1}/4 {row['regime']} B={slot['budget']}: {reason}; {e['verdict']}; correct={e['correct']}; evidence={e['evidence_backed_correct']}; credits={e['credits_spent']:.6f}; API upper={result['api_budget']['committed_upper_usd']}", flush=True)
            if reason == "api_ceiling" or must_halt(path, reason):
                log.event("campaign_halted", reason=reason)
                break
        else:
            log.event("campaign_finished", cases=4)
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
    parser.add_argument("--scaffolded", type=Path)
    parser.add_argument("--output-root", type=Path, default=science.RUNS)
    args = parser.parse_args()
    if args.render:
        print(json_text(render(args.render)) if (args.render/"cpu-comparisons.json").exists() else regenerate(args.render))
    else:
        if args.catalog is None or args.scaffolded is None:
            parser.error("--catalog and --scaffolded require explicit saved run directories")
        asyncio.run(run_catalog(args.catalog, args.scaffolded, args.output_root, mode="live" if args.live else "dry-run"))


if __name__ == "__main__":
    main()
