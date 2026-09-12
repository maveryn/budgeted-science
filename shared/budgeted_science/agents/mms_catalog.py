"""Six independent Luna/high MMS episodes; $2 maximum for the whole batch."""
import argparse
import asyncio
from dataclasses import replace
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from ..mms_verification.environment import score
from ..mms_verification.experiment import ROOT, RUNS, artifact_hashes, reconcile
from .mms_verification import MMSAdapter, MMSConfig, MMSInstance, regenerate, tool_definitions
from .records import RunLog, digest, json_text, read_events
from .reporting import _write
from .runner import provenance, run_episode
from .spending import pricing_for_model
from .verification_catalog import must_halt
from .verification_incremental_catalog import BatchBudget

CATALOG = RUNS / "20260912T191002Z-mms-cpu-fc4ad49335"


def read_catalog(path):
    path = Path(path).resolve()
    manifest = json.loads((path/"manifest.json").read_text(encoding="utf-8"))
    completion = json.loads((path/"completion.json").read_text(encoding="utf-8"))
    summary = json.loads((path/"summary.json").read_text(encoding="utf-8"))
    if (manifest["version"] != "mms-cpu-1" or summary["status"] != "complete"
            or digest(manifest) != completion["manifest_sha256"] or digest(summary) != completion["summary_sha256"]
            or artifact_hashes(path) != completion["artifact_sha256"]):
        raise ValueError("frozen CPU catalog integrity mismatch")
    reconcile(path, summary)
    for relative, expected in manifest["source_sha256"].items():
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest() != expected:
            raise ValueError("scientific implementation changed since CPU pilot")
    catalog = json.loads((path/"private/catalog.json").read_text(encoding="utf-8"))
    cases = catalog["cases"]
    if len(cases) != 6 or len({c["id"] for c in cases}) != 6:
        raise ValueError("expected six frozen studies")
    comparisons = {c["id"]: {} for c in cases}
    for row in summary["results"]:
        if row["budget"] == 10:
            if row["policy"] in comparisons[row["study_id"]]:
                raise ValueError("duplicate CPU comparison")
            comparisons[row["study_id"]][row["policy"]] = row
    expected = {"study_refinement", "fixed_diffusion", "fixed_suite", "study_aware", "early_reject"}
    if any(set(rows) != expected for rows in comparisons.values()):
        raise ValueError("missing CPU comparison")
    return cases, comparisons, {"path": str(path), "catalog_hash": digest(catalog),
                                "completion_sha256": hashlib.sha256((path/"completion.json").read_bytes()).hexdigest()}


def render(path):
    path = Path(path).resolve()
    seal = path/"integrity.json"
    if seal.exists():
        hashes = artifact_hashes(path)
        hashes.pop("integrity.json", None)
        if hashes != json.loads(seal.read_text(encoding="utf-8")):
            raise ValueError("batch artifact integrity mismatch")
    manifest = json.loads((path/"manifest.json").read_text(encoding="utf-8"))
    cases = {c["id"]: c for c in json.loads((path/"private/studies.json").read_text(encoding="utf-8"))}
    rows = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((path/"results").glob("*.json"))]
    comparisons = json.loads((path/"cpu-comparisons.json").read_text(encoding="utf-8"))
    for row in rows:
        e = row["evaluation"]
        expected = score(e["submission"], cases[row["case_id"]])
        if any(e[key] != value for key, value in expected.items()):
            raise ValueError("saved agent score mismatch")
        episode = Path(row["run"])
        if not episode.resolve().is_relative_to(path):
            raise ValueError("episode directory leaves batch")
        events, torn = read_events(episode)
        final = next((e for e in reversed(events) if e["kind"] == "run_finished"), None)
        if final is None or final["evaluation"] != row["evaluation"] or final["api_budget"] != row["api_budget"]:
            raise ValueError("episode events and batch results disagree")
    summary = {"mode": manifest["mode"], "planned": 6, "finished_attempts": len(rows),
               "unattempted_or_unfinalized": 6-len(rows), "rows": rows,
               "complete": sum(r["evaluation"]["complete"] for r in rows),
               "joint_correct": sum(r["evaluation"]["joint_correct"] for r in rows),
               "qoi_correct": sum(r["evaluation"]["qoi"]["correct"] for r in rows),
               "order_correct": sum(r["evaluation"]["order"]["correct"] for r in rows),
               "credits": sum(r["evaluation"]["scientific_status"]["spent"] for r in rows),
               "batch_budget": json.loads((path/"batch-budget.json").read_text(encoding="utf-8"))}
    lines = ["# Luna/high: six-study MMS verification", "",
             f"Mode: {manifest['mode']}; 10 scientific credits per independent episode; $2 whole-batch API ceiling.", "",
             f"Finalized attempts: {len(rows)}/6; value correct: {summary['qoi_correct']}/{len(rows)}; "
             f"order correct: {summary['order_correct']}/{len(rows)}; both correct: {summary['joint_correct']}/{len(rows)}.", "",
             "Six development studies share three physical systems, including an identical harmless control. "
             "One run per study, no automatic retries or case replacement. Abstentions/incomplete attempts are not correct answers. "
             "CPU feasibility was deliberately commissioned; its successful complete rule is not independent generalization evidence.", ""]
    if manifest["mode"] == "dry-run":
        lines += ["SCRIPTED OFFLINE FIXTURES, not model performance. Actual API spending is zero; token/cost records are synthetic.", ""]
    lines += ["| Study | Category | Value verdict | Order verdict | Both correct | Credits | Trace |",
              "|---|---|---|---|---|---:|---|"]
    for r in rows:
        e = r["evaluation"]
        trace = (Path(r["run"])/"transcript.md").relative_to(path).as_posix()
        lines.append(f"| {r['case_id']} | {r['category']} | {e['qoi']['verdict']} | {e['order']['verdict']} | {e['joint_correct']} | "
                     f"{e['scientific_status']['spent']:.4f} | [transcript]({trace}) |")
    lines += ["", "## Matched saved CPU controls at 10 credits", "",
              "| Policy | Value correct | Order correct | Both correct | Mean spent |", "|---|---:|---:|---:|---:|"]
    for policy in ("study_refinement", "fixed_diffusion", "fixed_suite", "study_aware", "early_reject"):
        cpu = [c[policy] for c in comparisons.values()]
        lines.append(f"| {policy} | {sum(r['evaluation']['qoi']['correct'] for r in cpu)}/6 | "
                     f"{sum(r['evaluation']['order']['correct'] for r in cpu)}/6 | {sum(r['evaluation']['joint_correct'] for r in cpu)}/6 | "
                     f"{sum(r['spent'] for r in cpu)/6:.4f} |")
    lines += ["", "## API accounting", "", "Conservative bounds, not an invoice; uncertain calls retain reservations.", "",
              "```json", json_text(summary["batch_budget"]), "```", ""]
    _write(path/"summary.json", json_text(summary)+"\n")
    _write(path/"report.md", "\n".join(lines))
    return summary


async def run_catalog(catalog_path=CATALOG, output_root=RUNS, *, mode, gateway_factory=None):
    if mode not in ("live", "dry-run") or mode == "live" and gateway_factory is not None:
        raise ValueError("explicit live/dry-run mode required; no live gateway override")
    cases, comparisons, source = read_catalog(catalog_path)
    config, money, frozen = MMSConfig(), BatchBudget("2.00"), provenance(ROOT)
    log = RunLog(output_root, "mms-luna-"+mode)
    slots = [{"case_id": c["id"], "study_hash": digest(c)} for c in cases]
    minimum = Decimal(pricing_for_model(config.model)["output_per_million_usd"])*config.max_output_tokens/Decimal(1_000_000)
    log.write_json("manifest.json", {"mode": mode, "config": config.public(), "cases": slots, "source_catalog": source,
        "api_maximum_usd": "2.00", "max_live_slots": 6, "pricing": pricing_for_model(config.model),
        "pricing_reverified": "2026-09-12", "pricing_source": "https://developers.openai.com/api/docs/pricing",
        "tool_schema_hash": digest(tool_definitions()), "automatic_retries": False, **frozen})
    log.write_json("private/studies.json", cases)
    log.write_json("cpu-comparisons.json", comparisons)
    log.write_json("batch-budget.json", money.status())
    print(log.path, flush=True)
    log.event("campaign_started", mode=mode, cases=6)
    try:
        for index, study in enumerate(cases):
            current = provenance(ROOT)
            if current["source_hashes"] != frozen["source_hashes"] or current["dependencies"] != frozen["dependencies"]:
                raise ValueError("implementation changed during frozen evaluation")
            if digest(study) != slots[index]["study_hash"]:
                raise ValueError("case changed during evaluation")
            allowance = money.reserve(index, minimum, config.api_ceiling_usd)
            if allowance is None:
                log.event("campaign_halted", reason="batch_api_ceiling", index=index)
                break
            log.write_json("batch-budget.json", money.status(), replace=True)
            log.write_json(f"slots/{index:02d}.json", {**slots[index], "status": "attempted", "api_ceiling_usd": str(allowance)})
            log.event("case_started", index=index, **slots[index])
            instance = MMSInstance(study, comparisons[study["id"]], source,
                                   {"campaign": str(log.path.resolve()), "slot": index, "ceiling_usd": "2.00"})
            path, reason = await run_episode(ROOT, log.path/"episodes", mode=mode,
                config=replace(config, api_ceiling_usd=str(allowance)), instance=instance,
                adapter=MMSAdapter(), gateway=gateway_factory(index) if gateway_factory else None)
            result = json.loads((path/"evaluation.json").read_text(encoding="utf-8"))
            money.settle(index, result["api_budget"])
            row = {**slots[index], "category": study["category"], "run": str(path.resolve()), **result}
            log.write_json(f"results/{index:02d}.json", row)
            log.write_json("batch-budget.json", money.status(), replace=True)
            log.event("case_finished", index=index, result=row)
            render(log.path)
            e = result["evaluation"]
            print(f"{index+1}/6: {reason}; value={e['qoi']['verdict']}; order={e['order']['verdict']}; both_correct={e['joint_correct']}; "
                  f"credits={e['scientific_status']['spent']:.4f}; API upper={result['api_budget']['committed_upper_usd']}", flush=True)
            if reason == "api_ceiling" or must_halt(path, reason):
                log.event("campaign_halted", reason=reason)
                break
        else:
            log.event("campaign_finished", cases=6)
        if provenance(ROOT)["source_hashes"] != frozen["source_hashes"]:
            raise ValueError("source changed before campaign completion")
    finally:
        log.write_json("batch-budget.json", money.status(), replace=True)
        render(log.path)
        log.close()
        log.write_json("integrity.json", artifact_hashes(log.path))
    return log.path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--live", action="store_true")
    modes.add_argument("--render", type=Path)
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--output-root", type=Path, default=RUNS)
    args = parser.parse_args()
    if args.render:
        print(json_text(render(args.render)) if (args.render/"cpu-comparisons.json").exists() else regenerate(args.render))
    else:
        asyncio.run(run_catalog(args.catalog, args.output_root, mode="live" if args.live else "dry-run"))


if __name__ == "__main__":
    main()
