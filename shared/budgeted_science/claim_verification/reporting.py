"""Offline reports from saved records only: no solver or tool execution."""
import json
from math import isclose
from pathlib import Path
import re
from ..agents.records import read_events


def numeric_quotes(submission, records):
    """Check explicit 'run-ID Q=number' citations; do not grade arbitrary prose."""
    text = "\n".join(submission.get(key, "") for key in ("diagnosis", "justification"))
    checks = []
    for run_id, value in re.findall(r"\b(run-[a-zA-Z0-9-]+)\s+Q=([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", text):
        q, expected = float(value), records.get(run_id)
        checks.append({"run_id": run_id, "quoted_q": q, "available": expected is not None,
                       "matches": expected is not None and isclose(q, expected, rel_tol=1e-9, abs_tol=1e-12)})
    return {"recognized_quotes": checks, "all_recognized_quotes_match": all(c["matches"] for c in checks),
            "semantic_grounding_scored": False,
            "scope": "Only explicit run-ID Q=number citations; other prose and numbers are not graded."}


def render_episode(path):
    path = Path(path)
    events, torn = read_events(path)
    lines = ["# Scripted verification transcript", "",
             "Offline fixture, not an LLM investigation. API expenditure: $0.", ""]
    for event in events:
        if event["kind"] == "prompt":
            lines.extend(["## Task prompt", "", event["text"], ""])
        elif event["kind"] == "assistant_message":
            lines.extend(["## Scripted assistant", "", event["text"], ""])
        elif event["kind"] in ("tool_call", "tool_result", "duplicate_call"):
            lines.extend([f"### {event['kind']}", "", "~~~json",
                          json.dumps({k: v for k, v in event.items() if k not in ("utc", "sequence")},
                                     indent=2, ensure_ascii=False), "~~~", ""])
    finished = next((e for e in reversed(events) if e["kind"] == "finished"), None)
    evaluation = finished["evaluation"] if finished else None
    if torn:
        lines.extend(["A torn final event was preserved; this transcript omits its incomplete JSON.", ""])
    if not finished:
        lines.extend(["Run has no durable completion event; outcome is incomplete.", ""])
    (path / "transcript.md").write_text("\n".join(lines), encoding="utf-8")
    report = ["# Scripted verification outcome", "",
              "**This is a software fixture, not measured agent performance.**", "",
              "Actual API calls: 0. API expenditure: $0.", ""]
    if evaluation:
        report.extend(["~~~json", json.dumps(evaluation, indent=2), "~~~", "",
                       "## Mechanical citation checks", "",
                       "~~~json", json.dumps(finished.get("numeric_quotes", {}), indent=2), "~~~"])
    else:
        report.append("Incomplete: no durable final evaluation is available.")
    (path / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return {"path": str(path), "complete": bool(finished), "torn_tail": torn,
            "evaluation": evaluation}


def render_catalog(path):
    path = Path(path)
    catalog = json.loads((path / "private/catalog.json").read_text(encoding="utf-8"))
    effects_path = path / "private/check_effects.json"
    effects = json.loads(effects_path.read_text(encoding="utf-8")) if effects_path.exists() else []
    lines = ["# Verification development catalog", "",
             "Six development systems, not 30 independent systems. No model evaluation.",
             "The 5-credit budget permits both checks; this does not demonstrate a need for adaptive auditing.", "",
             f"Complete catalog: {catalog['complete']}. Studies: {len(catalog['studies'])}.", "",
             "| Case | System seed | Category | Format | Reported Q | Reference Q | Error % | Label |",
             "|---|---:|---|---|---:|---:|---:|---|"]
    for study in catalog["studies"]:
        p = study["private"]
        lines.append(f"| {study['case_id']} | {p['seed']} | {p['category']} | {study['format']} | "
                     f"{study['reported_q']:.10g} | {p['reference_q']:.10g} | "
                     f"{100*p['relative_error']:.6f} | {'ACCEPT' if p['claim_valid'] else 'REJECT'} |")
    lines.extend(["", "## Check effects", "",
                  "Errors below use the private reference for commissioning. They are not agent-visible error bounds.", "",
                  "| Case | Check | Credits | Result Q | Reference error % |",
                  "|---|---|---:|---:|---:|"])
    for effect in effects:
        lines.append(f"| {effect['case_id']} | {effect['check']} | {effect['spent']:.0f} | "
                     f"{effect['q']:.10g} | {100*effect['error']:.6f} |")
    if catalog["failures"]:
        lines.extend(["", "## Commissioning failures", "", "~~~json",
                      json.dumps(catalog["failures"], indent=2), "~~~"])
    (path / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary = {"studies": len(catalog["studies"]), "systems": len(catalog["systems"]),
               "complete": catalog["complete"], "agent_episodes": 0, "api_usd": 0,
               "valid_claims": sum(s["private"]["claim_valid"] for s in catalog["studies"]),
               "invalid_claims": sum(not s["private"]["claim_valid"] for s in catalog["studies"]),
               "check_effect_records": len(effects)}
    (path / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def render(path):
    path = Path(path)
    return render_catalog(path) if (path / "private/catalog.json").is_file() else render_episode(path)
