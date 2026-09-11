"""Offline rendering for live/fake verification episodes."""
import json
from pathlib import Path
from .records import json_text
from .reporting import _write, regenerate as generic_regenerate


def write_report(path, manifest, events, finished, status):
    c = manifest["public_configuration"]
    report = ["# Claim verification agent evaluation", "",
              f"Mode: {manifest['mode']}. Model: {c['model']}. Reasoning: {c['reasoning_effort']}.",
              f"Termination: {status}. Scientific budget: 5. API ceiling: USD {c['api_ceiling_usd']}.", "",
              "One development case, not evidence of general verification ability. "
              "The original claim is scored; explanation quality is not semantically graded.", ""]
    if manifest["mode"] == "dry-run":
        report += ["**Scripted offline fixture: actual API cost is zero; token accounting below is synthetic.**", ""]
    if finished:
        e, b = finished["evaluation"], finished.get("fixed_policy")
        report += ["| Method | Verdict | Correct | Audit credits |", "|---|---|---|---:|",
                   f"| Model / scripted fake | {e['verdict']} | {e['correct']} | {e['spent']:g} |"]
        if b:
            be = b["evaluation"]
            report.append(f"| Fixed two-check verifier | {be['verdict']} | {be['correct']} | {be['spent']:g} |")
        report += ["", "## Actual submission", "", "~~~json",
                   json_text(next((x["output"]["result"]["submission"] for x in reversed(events)
                                   if x["kind"] == "tool_result" and x.get("role") == "agent"
                                   and x.get("output", {}).get("result", {}).get("status") == "submitted"), None)),
                   "~~~", "", "## Private evaluation", "", "~~~json", json_text(e), "~~~", "",
                   "## API accounting", "", "Conservative bounds, not an invoice. Uncertain usage retains reservations.",
                   "", "~~~json", json_text(finished["api_budget"]), "~~~", ""]
        _write(path / "evaluation.json", json_text({k: finished[k] for k in
               ("termination_reason", "evaluation", "fixed_policy", "api_budget",
                "model_responses", "elapsed_seconds")}) + "\n")
    else:
        report += ["No durable final evaluation. No tools were rerun to invent a score.", ""]
    report += ["- [Transcript](transcript.md)", "- [Complete event log](events.jsonl)",
               "- [Frozen prompt](prompts.json)", "- [Tool schemas](tools.json)",
               "- [Manifest; contains private harness metadata](manifest.json)", ""]
    _write(path / "report.md", "\n".join(report))
    return path / "transcript.md", path / "report.md"


def regenerate(path):
    paths = generic_regenerate(path, report_writer=write_report)
    transcript = Path(path) / "transcript.md"
    text = transcript.read_text(encoding="utf-8")
    _write(transcript, text.replace("# Planning episode transcript", "# Claim verification episode transcript", 1))
    return paths
