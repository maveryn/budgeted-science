"""One sequential, fully logged Luna evaluation of the existing 30-study catalog."""
import argparse
import asyncio
from copy import deepcopy
from decimal import Decimal
import json
import os
from pathlib import Path
import statistics

from ..claim_verification.studies import validate_study
from .records import RunLog, digest, json_text, read_events
from .runner import provenance, run_episode
from .spending import pricing_for_model
from .verification import VerificationAdapter, VerificationConfig, VerificationInstance, tool_definitions
from .verification_cli import ROOT, CATALOG


def read_catalog(path):
    path = Path(path).resolve()
    catalog = json.loads((path / "private/catalog.json").read_text(encoding="utf-8"))
    integrity = json.loads((path / "catalog_integrity.json").read_text(encoding="utf-8"))
    ids = [s["case_id"] for s in catalog["studies"]]
    if not catalog["complete"] or digest(catalog) != integrity["catalog_digest"]:
        raise ValueError("catalog incomplete or changed")
    if len(ids) != 30 or len(set(ids)) != 30:
        raise ValueError("expected exactly 30 unique studies")
    studies = [validate_study(deepcopy(s)) for s in catalog["studies"]]
    if any(digest(s) != integrity["case_digests"][s["case_id"]] for s in studies):
        raise ValueError("study integrity mismatch")
    return studies, integrity["catalog_digest"]


def summarize(rows):
    n = len(rows)
    valid = sum(r["claim_valid"] for r in rows)
    invalid = n - valid
    return {"attempts": n, "correct": sum(r["correct"] for r in rows),
            "valid_claims": valid, "invalid_claims": invalid,
            "false_accept": sum(r["false_accept"] for r in rows),
            "false_reject": sum(r["false_reject"] for r in rows),
            "covered": sum(r["covered"] for r in rows),
            "abstained": sum(r["abstained"] for r in rows),
            "incomplete": sum(r["incomplete"] for r in rows),
            "audit_credits": sum(r["spent"] for r in rows),
            "mean_audit_credits": statistics.mean(r["spent"] for r in rows) if rows else None,
            "agent_seconds": sum(r["elapsed_seconds"] for r in rows),
            "mean_agent_seconds": statistics.mean(r["elapsed_seconds"] for r in rows) if rows else None,
            "input_tokens": sum(r["input_tokens"] for r in rows),
            "output_tokens": sum(r["output_tokens"] for r in rows),
            "reasoning_tokens": sum(r["reasoning_tokens"] for r in rows),
            "api_committed_upper_usd": str(sum((Decimal(r["api_upper_usd"]) for r in rows), Decimal(0))),
            "api_measured_lower_usd": str(sum((Decimal(r["api_lower_usd"]) for r in rows), Decimal(0))),
            "uncertain_reserved_usd": str(sum((Decimal(r["uncertain_reserved_usd"]) for r in rows), Decimal(0))),
            "baseline_correct": sum(r["baseline_correct"] for r in rows)}


def result_row(study, path, campaign, result):
    e, money = result["evaluation"], result["api_budget"]
    usage = money["measured_responses"]
    return {"case_id": study["case_id"], "system_seed": study["private"]["seed"],
            "category": study["private"]["category"], "format": study["format"],
            "run": Path(os.path.relpath(path, campaign)).as_posix(),
            "termination_reason": result["termination_reason"],
            **{k: e[k] for k in ("claim_valid", "verdict", "correct", "covered", "abstained",
                                "false_accept", "false_reject", "incomplete", "spent", "relative_error")},
            "elapsed_seconds": result["elapsed_seconds"], "model_responses": result["model_responses"],
            "api_upper_usd": money["committed_upper_usd"],
            "api_lower_usd": str(sum((Decimal(v["standard_cost_lower_usd"]) for v in usage), Decimal(0))),
            "uncertain_reserved_usd": money["uncertain_reserved_usd"],
            "input_tokens": sum(v["usage"]["input_tokens"] for v in usage),
            "output_tokens": sum(v["usage"]["output_tokens"] for v in usage),
            "reasoning_tokens": sum(v["usage"].get("output_tokens_details", {}).get("reasoning_tokens", 0) for v in usage),
            "baseline_correct": bool((result.get("fixed_policy") or {}).get("evaluation", {}).get("correct", False))}


def must_halt(path, reason):
    ordinary = {"submitted", "api_ceiling", "deadline", "response_limit", "tool_request_limit",
                "no_submission", "model_output_incomplete", "refusal", "api_response_failed",
                "stream_ended_without_response", "api_stream_error", "request_or_runner_error"}
    if reason not in ordinary:
        return True
    events, torn = read_events(path)
    if torn:
        return True
    for e in events:
        if e["kind"] != "run_error" or e.get("stage") == "client_close":
            continue
        error = e.get("error", {})
        if error.get("status_code") in (401, 403):
            return True
        if error.get("class") not in ("APIConnectionError", "APITimeoutError", "OSError", "RateLimitError"):
            return True
    return False


def render(path):
    path = Path(path)
    m = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    rows = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((path / "results").glob("*.json"))]
    summary = {"mode": m["mode"], "planned_cases": len(m["cases"]), "overall": summarize(rows)}
    for field in ("category", "format", "system_seed"):
        summary[field] = {str(key): summarize([r for r in rows if r[field] == key])
                          for key in sorted({r[field] for r in rows})}
    (path / "summary.json").write_text(json_text(summary) + "\n", encoding="utf-8")
    total = summary["overall"]
    lines = ["# Luna claim-verification catalog evaluation", "",
             f"Mode: {m['mode']}; model: gpt-5.6-luna; reasoning: high.",
             f"Recorded attempts: {len(rows)}/{len(m['cases'])}. Correct: {total['correct']}/{len(rows)}.",
             "Existing development catalog: six systems, five variants each; not 30 independent systems.", "",
             "Five audit credits per episode; no full-budget requirement or savings bonus. "
             "All attempts count in the accuracy denominator. An abstention is completed but not correct.", ""]
    if m["mode"] == "dry-run":
        lines += ["Scripted fake responses, NOT model performance. Actual API expenditure is zero; ledger usage is synthetic.", ""]
    lines += ["## Aggregate", "", "~~~json", json_text(total), "~~~", "",
              "Cost bounds include unresolved reservations, not an invoice. Baselines have independent ledgers.", "",
              "## By study category", "", "| Category | Correct | False accept | False reject | Abstain | Incomplete |",
              "|---|---:|---:|---:|---:|---:|"]
    for key, s in summary["category"].items():
        lines.append(f"| {key} | {s['correct']}/{s['attempts']} | {s['false_accept']} | {s['false_reject']} | {s['abstained']} | {s['incomplete']} |")
    lines += ["", "## Individual cases", "", "| Case | Category | Format | Verdict | Correct | Credits | Transcript |",
              "|---|---|---|---|---|---:|---|"]
    for r in rows:
        lines.append(f"| {r['case_id']} | {r['category']} | {r['format']} | {r['verdict']} | {r['correct']} | {r['spent']:g} | [Read]({r['run']}/transcript.md) |")
    lines += ["", "Each episode retains prompts, schemas, API requests/responses/stream events, tool results, numerical "
              "artifacts and private scoring. Explanations are retained, not semantically graded. "
              "Both checks fit the budget; a correct verdict need not demonstrate adaptive allocation.", ""]
    (path / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


async def run_catalog(catalog_path, output_root, *, mode, gateway_factory=None):
    if mode not in ("dry-run", "live") or (mode == "live" and gateway_factory is not None):
        raise ValueError("invalid mode or live gateway override")
    studies, catalog_hash = read_catalog(catalog_path)
    config = VerificationConfig(model="gpt-5.6-luna")
    log = RunLog(output_root, "luna-catalog-" + mode)
    frozen = provenance(ROOT)
    cases = [{"case_id": s["case_id"], "study_hash": digest(s), "system_seed": s["private"]["seed"],
              "category": s["private"]["category"], "format": s["format"]} for s in studies]
    log.write_json("manifest.json", {"mode": mode, "config": config.public(), "cases": cases,
        "catalog_path": str(Path(catalog_path).resolve()), "catalog_digest": catalog_hash,
        "max_live_slots": len(studies), "api_maximum_usd": str(Decimal(config.api_ceiling_usd) * len(studies)),
        "pricing": pricing_for_model(config.model), "tool_schema_hash": digest(tool_definitions(config)),
        "order": "existing catalog order", "automatic_retries": False, **frozen})
    print(log.path, flush=True)
    log.event("catalog_started", cases=len(studies), mode=mode)
    try:
        for index, study in enumerate(studies):
            current = provenance(ROOT)
            if current["source_hashes"] != frozen["source_hashes"] or current["dependencies"] != frozen["dependencies"]:
                raise ValueError("implementation changed during frozen evaluation")
            if digest(study) != cases[index]["study_hash"]:
                raise ValueError("frozen study changed during evaluation")
            # Exclusive, durable marker BEFORE any possible API request. Never retry an attempted slot.
            log.write_json(f"slots/{index:02d}.json", {"case_id": study["case_id"], "status": "attempted",
                           "api_ceiling_usd": config.api_ceiling_usd})
            log.event("case_started", index=index, case_id=study["case_id"])
            instance = VerificationInstance(study, str(Path(catalog_path).resolve()), catalog_hash,
                                            "all 30 development cases in existing catalog order")
            # Keep episode folders beside the campaign to stay below Windows path limits.
            path, reason = await run_episode(ROOT, output_root,
                mode=mode, config=config, instance=instance, adapter=VerificationAdapter(),
                gateway=gateway_factory(index) if gateway_factory else None)
            result = json.loads((path / "evaluation.json").read_text(encoding="utf-8"))
            row = result_row(study, path, log.path, result)
            if Decimal(row["api_upper_usd"]) > Decimal(config.api_ceiling_usd):
                raise ValueError("episode accounting exceeded ceiling")
            log.write_json(f"results/{index:02d}.json", row)
            log.event("case_finished", index=index, case_id=study["case_id"], result=row)
            summary = render(log.path)
            if Decimal(summary["overall"]["api_committed_upper_usd"]) > Decimal(90):
                raise ValueError("campaign accounting exceeded ceiling")
            print(f"{index+1}/{len(studies)} {study['case_id']}: {reason}; verdict={row['verdict']}; "
                  f"correct={row['correct']}; credits={row['spent']:g}; API upper={row['api_upper_usd']}", flush=True)
            if must_halt(path, reason):
                log.event("catalog_halted", reason=reason, case_id=study["case_id"])
                break
        else:
            log.event("catalog_finished", cases=len(studies))
    finally:
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
    parser.add_argument("--output-root", type=Path, default=ROOT / "demos/claim_verification/runs")
    args = parser.parse_args()
    if args.render:
        print(json_text(render(args.render)))
        return
    asyncio.run(run_catalog(args.catalog, args.output_root, mode="live" if args.live else "dry-run"))


if __name__ == "__main__":
    main()
