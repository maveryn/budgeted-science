"""CPU-only shared-baseline evaluation on the six frozen verification studies.

Run: python -m budgeted_science.paired_claim_audit.adaptive_target_three_pilot run
Render saved logs: ... render RUN_DIRECTORY
No API transport, credentials, model reruns, or catalog regeneration.
"""

import argparse
from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import time

from ..agents import target_three_claims as existing
from ..agents.records import RunLog, digest, json_text, read_events
from ..resource_planning.adaptive_design import NAME, SETTINGS
from ..resource_planning.config import harder_config
from ..resource_planning.experiment import REPO, source_hashes, versions
from .adaptive_target_three_policy import run_policy


RUNS = REPO / "demos/paired_claim_audit/runs"
PREPARED = RUNS / "20260913T085926Z-target-three-prepared-cdb738cbfa"
MODELS = RUNS / "20260913T093320Z-target-three-models-prepared-e30c1fbe8c/campaigns/20260913T094518Z-live-0262ddc444/results.json"
LUNA_VIEW = RUNS / "20260913T105527Z-target-three-luna-case4-retry-live-90354c03ce/retry_inclusive_six_case_view.json"
CATALOG_HASH = "086f913625f20a5c49eac56ad8cdafeec19fa2ef5468fef2d9d8b24fca7f1d8b"
PLANNING_POLICY_HASH = "bd4853332b31b6dc2d874cf735a78821ec13c7be888c4dbcf4fdc032359e2617"
SCIENCE_SOURCES = (
    "resource_planning/config.py", "resource_planning/environment.py",
    "multi_claim_audit/core.py", "multi_claim_audit/mixed.py",
    "paired_claim_audit/core.py", "paired_claim_audit/followup_core.py",
    "paired_claim_audit/target_three.py", "agents/target_three_claims.py",
    "agents/multi_claim_audit.py",
)


@dataclass(frozen=True)
class CPUConfig:
    scientific_budget: int = 32
    max_tool_requests: int = 60
    deadline_seconds: int = 300


def verify_contract(manifest):
    """Check current executable science and schemas against the saved pilot."""
    if digest(existing.tool_definitions()) != manifest["tools_hash"]:
        raise ValueError("saved verification tool schemas changed")
    for relative in SCIENCE_SOURCES:
        key = "shared/budgeted_science/" + relative
        if hashlib.sha256((REPO / key).read_bytes()).hexdigest() != manifest["source_hashes"].get(key):
            raise ValueError("saved numerical/tool implementation changed: " + key)


def read_inputs():
    """Private harness import. Only public report/tools reach the policy."""
    hashes = {}
    def read(path):
        path = Path(path).resolve()
        data = path.read_bytes()
        hashes[str(path)] = hashlib.sha256(data).hexdigest()
        return json.loads(data)
    manifest, catalog = read(PREPARED / "manifest.json"), read(PREPARED / "catalog.json")
    verify_contract(manifest)
    if digest(catalog) != CATALOG_HASH or manifest["catalog_hash"] != CATALOG_HASH:
        raise ValueError("frozen verification catalog changed")
    cases = catalog["cases"]
    if len(cases) != 6 or len(manifest["slots"]) != 6 or len({c["case_id"] for c in cases}) != 6:
        raise ValueError("expected exactly six original studies")
    comparisons = []
    by_id = {c["case_id"]: c["study"] for c in cases}
    for case, slot in zip(cases, manifest["slots"]):
        payload = read(PREPARED / "slots" / slot["slot"] / "payload.json")
        if (slot["case_id"] != case["case_id"] or digest(payload) != slot["payload_hash"]
                or payload["study"] != case["study"]
                or case["study"]["public"]["environment"] != harder_config(32).public()):
            raise ValueError("case order, payload, or resource configuration changed")
        cpu = payload["comparisons"]["continuous_local_fit"]
        saved_cpu = read(Path(cpu["path"]) / "evaluation.json")
        if cpu != saved_cpu:
            raise ValueError("saved CPU comparison changed")
        comparisons.append({"case_id": case["case_id"], "method": "continuous_local_fit",
                            "evaluation": cpu, "path": cpu["path"]})
    models, luna = read(MODELS), read(LUNA_VIEW)
    selected = list(models) + [{**r, "model": "gpt-5.6-luna (completed-study view)"}
                               for r in luna["results"]]
    expected = {(case_id, model) for case_id in by_id for model in (
        "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna (completed-study view)")}
    if len(selected) != 18 or {(r["case_id"], r["model"]) for r in selected} != expected:
        raise ValueError("saved model/case mapping changed")
    for row in selected:
        original = read(Path(row["path"]) / "evaluation.json")
        study = read(Path(row["path"]) / "private/study.json")
        if study != by_id[row["case_id"]] or original["evaluation"] != row["evaluation"]:
            raise ValueError("saved model study or evaluation changed")
        comparisons.append({"case_id": row["case_id"], "method": row["model"],
                            "evaluation": row["evaluation"], "path": row["path"]})
    return cases, comparisons, hashes, luna["label"]


def render_episode(path):
    """Only saved JSON/events; no physical execution or numerical fitting."""
    path = Path(path)
    existing.previous.legacy.render_cpu(path)
    transcript = (path / "transcript.md").read_text(encoding="utf-8")
    transcript = transcript.replace("# Fixed CPU multi-claim audit", "# Adaptive multifidelity CPU verification", 1)
    transcript = transcript.replace("Scripted classical control;", "Adaptive numerical control;", 1)
    (path / "transcript.md").write_text(transcript, encoding="utf-8")
    events, torn = read_events(path)
    lines = ["# Complete acquisition trace", "", "| Step | Action | Location | Charge | Remaining | Gain / credit |",
             "|---:|---|---|---:|---:|---:|"]
    for event in events:
        if event["kind"] != "adaptive_design_acquired":
            continue
        action, result = event["action"], event["result"]
        location = action.get("theta", [action.get("variable"), action.get("time")])
        lines.append(f"| {event['step']+1} | {action.get('fidelity','measurement')} | {location} | {result.get('charge')} | {result.get('remaining')} | {action['score']:.8g} |")
    if torn:
        lines += ["", "An interrupted final event was retained."]
    (path / "trace.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_case(case, root):
    config = CPUConfig()
    log = RunLog(Path(root) / "episodes", case["case_id"])
    started, episode, reason, details = time.monotonic(), None, "cpu_incomplete", None
    try:
        log.write_json("manifest.json", {"mode": "cpu", "method": NAME, "case_id": case["case_id"],
                                        "configuration": asdict(config), "settings": SETTINGS,
                                        "api_expenditure_usd": 0})
        episode = existing.Episode(config, existing.Instance(case["study"]), log, started + config.deadline_seconds)
        initial = episode.environment.evidence()
        messages = [{"role": "user", "content": "Audit the three target claims using the shared "
                     "adaptive numerical investigator. 32 credits, prices 1/8/12. "
                     "Plug-in verdicts from fitted predictions; no confidence certificate.\n\n" + json_text(initial)}]
        log.write_json("prompts.json", messages)
        log.write_json("tools.json", existing.tool_definitions())
        log.event("prompt_frozen", messages=messages)
        count = 0
        def call(name, **args):
            nonlocal count
            count += 1
            return episode.execute(f"cpu-{count}", name, json.dumps(args, allow_nan=False))
        try:
            details = run_policy(call, deepcopy(case["study"]["public"]), log.event,
                                 started + config.deadline_seconds)
            reason = "submitted" if episode.submission is not None else "cpu_incomplete"
        except Exception as exc:
            log.event("cpu_failure", error=log.redactor.error(exc))
        evaluation = episode.evaluate()
        status = evaluation["scientific_status"]
        counts = {name: sum(r["kind"] == action for r in status["ledger"])
                  for name, action in (("low","simulate_low"),("high","simulate_high"),("measurement","measure_target"))}
        charged = counts["low"] + 8*counts["high"] + 12*counts["measurement"]
        if charged != status["spent"] or charged > 32:
            raise ValueError("scientific ledger mismatch")
        row = {"case_id": case["case_id"], "method": NAME, "evaluation": evaluation,
               "termination_reason": reason, "resource_counts": counts, "accounting_valid": True,
               "elapsed_seconds": time.monotonic()-started, "api_expenditure_usd": 0,
               "path": str(log.path), "details": details}
        log.write_json("evaluation.json", row)
        log.event("cpu_finished", result=row)
        return row
    finally:
        log.close()
        render_episode(log.path)


def aggregate(rows):
    groups = []
    for method in dict.fromkeys(r["method"] for r in rows):
        group = [r["evaluation"] for r in rows if r["method"] == method]
        total = sum(r["total"] for r in group)
        sums = {k: sum(r[k] for r in group) for k in (
            "correct","wrong","abstained","incomplete_claims","false_acceptances","false_rejections")}
        groups.append({"method": method, "studies": len(group), "completed": sum(r["completed"] for r in group),
                       "total": total, **sums, "coverage": (sums["correct"]+sums["wrong"])/total,
                       "utility": sums["correct"]-2*sums["wrong"],
                       "credits": sum(r["scientific_status"]["spent"] for r in group)})
    return groups


def render(path):
    path = Path(path)
    manifest = json.loads((path / "manifest.json").read_text())
    events, torn = read_events(path)
    rows = [r["result"] for r in events if r["kind"] == "case_finished"]
    comparisons = json.loads((path / "saved_comparisons.json").read_text())
    complete = (not torn and len(rows) == len(manifest["cases"]) and bool(events)
                and events[-1]["kind"] == "finished" and events[-1]["unchanged"])
    recorded = {r["case_id"] for r in rows}
    attempted = recorded | {e["case_id"] for e in events if e["kind"] == "case_started"}
    matched = [r for r in comparisons if r["case_id"] in recorded]
    groups = aggregate(rows + comparisons)
    summary = {"complete": complete, "rows": rows, "groups": groups, "luna_view": manifest["luna_view"],
               "api_expenditure_usd": 0, "attempted_cases": len(attempted),
               "attempted_without_result": sorted(attempted-recorded),
               "unattempted_cases": [c for c in manifest["cases"] if c not in attempted],
               "matched_recorded_groups": aggregate(rows + matched)}
    (path / "summary.json").write_text(json_text(summary) + "\n", encoding="utf-8")
    lines = ["# Shared adaptive baseline: verification", "",
             f"Campaign complete: {complete}. Attempted {len(attempted)}/{len(manifest['cases'])}; "
             f"recorded outcomes {len(rows)}; attempted without a final record {len(attempted-recorded)}.", ""]
    if not complete:
        lines += ["**Partial campaign:** the full-cohort table below includes every saved comparison, "
                  "but only available new outcomes. Do not compare unequal denominators as matched results. "
                  "The JSON also contains comparisons restricted to cases with a recorded new outcome. "
                  "An interrupted attempt without a final record has unknown expenditure here; its partial "
                  "episode logs are retained.", ""]
    lines += ["| Method | Correct | Wrong | Abstain | Incomplete claims | Utility | Credits |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for g in groups:
        lines.append(f"| {g['method']} | {g['correct']}/{g['total']} | {g['wrong']} | {g['abstained']} | {g['incomplete_claims']} | {g['utility']} | {g['credits']} |")
    lines += ["", "| Study | Case | Correct / 3 | Wrong | Abstain | Low/high/measurement | Credits | Seconds |",
              "|---:|---|---:|---:|---:|---|---:|---:|"]
    for index, row in enumerate(rows, 1):
        ev = row["evaluation"]
        lines.append(f"| {index} | {row['case_id']} | {ev['correct']} | {ev['wrong']} | {ev['abstained']} | {row['resource_counts']} | {ev['scientific_status']['spent']} | {row['elapsed_seconds']:.3f} |")
        render_episode(row["path"])
    lines += ["", "## Claim-level results", "", "| Study | Claim | Type | Estimated quantity | Reference | Verdict | Truth | Correct |",
              "|---:|---|---|---:|---:|---|---|---|"]
    for index, row in enumerate(rows, 1):
        episode_events, _ = read_events(row["path"])
        fits = [e for e in episode_events if e["kind"] == "adaptive_audit_prediction"]
        quantities = fits[-1]["estimated_quantities"] if fits else {}
        for c in row["evaluation"]["rows"]:
            lines.append(f"| {index} | {c['id']} | {c['kind']} | {quantities.get(c['kind'])} | {c['reference_value']} | {c['verdict']} | {c['truth']} | {c['correct']} |")
    lines += ["", "## Full traces", ""]
    lines += [f"- Study {i}: [transcript]({Path(r['path']).as_posix()}/transcript.md), [acquisitions]({Path(r['path']).as_posix()}/trace.md)"
              for i,r in enumerate(rows,1)]
    lines += ["", "The planning acquisition algorithm and settings are unchanged; only the final output is adapted.",
              "Predictions are fitted approximations, not unpaid high-fidelity solves. No LLM runs were repeated.",
              "Six reused development worlds form three related pairs, not six independent held-out systems.",
              "Luna comparison: " + manifest["luna_view"] + ".", ""]
    (path / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def campaign(output=RUNS):
    cases, comparisons, inputs, luna_view = read_inputs()
    sources = source_hashes()
    if sources["shared/budgeted_science/resource_planning/adaptive_design.py"] != PLANNING_POLICY_HASH:
        raise ValueError("shared planning policy changed; this comparison requires the original frozen algorithm")
    log = RunLog(output, "adaptive-target-three-cpu")
    try:
        log.write_json("manifest.json", {"method": NAME, "configuration": asdict(CPUConfig()),
                                        "settings": SETTINGS, "source_hashes": sources, "versions": versions(),
                                        "input_hashes": inputs, "cases": [c["case_id"] for c in cases],
                                        "catalog_hash": CATALOG_HASH, "luna_view": luna_view,
                                        "api_expenditure_usd": 0})
        log.write_json("saved_comparisons.json", comparisons)
        log.event("started", cases=6)
        for i, case in enumerate(cases, 1):
            log.event("case_started", case_id=case["case_id"], study_number=i)
            result = run_case(case, log.path)
            log.event("case_finished", result=result)
            ev = result["evaluation"]
            print(i, case["case_id"], result["termination_reason"], "correct", ev["correct"],
                  "wrong", ev["wrong"], "abstain", ev["abstained"], result["resource_counts"], flush=True)
        unchanged = sources == source_hashes() and all(
            hashlib.sha256(Path(p).read_bytes()).hexdigest() == sha for p,sha in inputs.items())
        log.event("finished", unchanged=unchanged)
        if not unchanged:
            raise ValueError("source or preserved input changed during evaluation")
    finally:
        log.close()
        render(log.path)
    print(log.path, flush=True)
    return log.path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run","render"))
    parser.add_argument("path", type=Path, nargs="?")
    args = parser.parse_args()
    if args.mode == "render":
        if not args.path:
            parser.error("render requires a saved run directory")
        render(args.path)
    else:
        if args.path:
            parser.error("run creates its own unique output directory")
        campaign()


if __name__ == "__main__":
    main()
