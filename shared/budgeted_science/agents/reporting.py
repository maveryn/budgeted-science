"""Regenerate readable artifacts exclusively from local audit records."""

import json
import os
from pathlib import Path
from uuid import uuid4

from .records import json_text, read_events


def _write(path, text):
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def regenerate(path, *, report_writer=None):
    path = Path(path).resolve()
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    events, torn = read_events(path)
    finished = next((e for e in reversed(events) if e["kind"] == "run_finished"), None)
    sent_results = set()
    for event in events:
        if event["kind"] == "api_request_sent":
            sent_results.update(event.get("tool_output_sequences", []))
    lines = ["# Planning episode transcript", "",
             f"Mode: {manifest['mode']}. Model setting: {manifest['public_configuration']['model']}; reasoning: high.", "",
             "All API-visible material is retained in [events.jsonl](events.jsonl) and the api/ archive. "
             "Raw internal reasoning is not exposed. Encrypted reasoning is retained as opaque data, not readable thoughts.", "",
             "Tool results marked sent were included in an attempted subsequent API request; network delivery is not guaranteed. "
             "The final submission acknowledgment is saved locally without an extra generation.", ""]
    if manifest["mode"] == "dry-run":
        lines += ["**SCRIPTED OFFLINE RUN: no LLM was evaluated and no API request was billed.**", ""]
    completed = set()
    for e in events:
        kind = e["kind"]
        if kind == "prompt_frozen":
            for message in e["messages"]:
                lines += [f"## {message['role'].capitalize()} prompt", "", message["content"], ""]
            lines += ["Tool definitions: [tools.json](tools.json).", ""]
        elif kind == "api_response":
            completed.add(e["request_id"])
            lines += [f"## Response {e['request_id']}", "", f"Full response: [{e['artifact']}]({e['artifact']}).", ""]
            for item in e["response"].get("output", []):
                if item.get("type") == "reasoning":
                    for summary in item.get("summary", []):
                        lines += ["Returned reasoning summary:", "", summary.get("text", json_text(summary)), ""]
                    if item.get("encrypted_content"):
                        lines += ["Opaque encrypted reasoning item preserved in the response archive.", ""]
                elif item.get("type") == "message":
                    for content in item.get("content", []):
                        lines += [content.get("text", content.get("refusal", json_text(content))), ""]
                elif item.get("type") == "function_call":
                    lines += [f"Model tool-call item: {item.get('name')} ({item.get('call_id')}).", "",
                              "```json", item.get("arguments", ""), "```", ""]
                else:
                    lines += ["Additional API output item:", "", "```json", json_text(item), "```", ""]
        elif kind == "tool_requested" and e["role"] == "agent":
            lines += [f"### Tool request: {e['name']} ({e['call_id']})", "", "```json", e["arguments"], "```", ""]
        elif kind == "tool_result" and e["role"] == "agent":
            delivered = "sent in a subsequent request" if e["sequence"] in sent_results else "saved locally; not sent in a subsequent request"
            lines += [f"Tool result ({delivered}):", "", "```json", json_text(e["output"]), "```", ""]
        elif kind == "simulation_finished" and e["role"] == "agent":
            lines += [f"Underlying numerical artifact for {e['parent_call']}: [{e['result_id']}]({e['artifact']}).", ""]
        elif kind in ("run_error", "interruption"):
            lines += ["### Interruption / failure", "", "```json", json_text(e), "```", ""]
    partial = [e for e in events if e["kind"] == "api_stream_event" and e["request_id"] not in completed]
    if partial:
        lines += ["## Interrupted / unfinished stream events", "", "These are partial API-visible events, not a completed response.", ""]
        for e in partial:
            lines += ["```json", json_text(e["event"]), "```", ""]
    if torn:
        lines += ["Warning: an incomplete final JSONL line was ignored; the original log is unchanged.", ""]
    status = finished["termination_reason"] if finished else "interrupted_without_finalization"
    lines += [f"Termination: {status}.", ""]
    _write(path / "transcript.md", "\n".join(lines))

    if report_writer is not None:
        return report_writer(path, manifest, events, finished, status)

    report = ["# Planning episode evaluation", "", f"Mode: {manifest['mode']}. Termination: **{status}**.", ""]
    configuration = manifest["public_configuration"]
    report += [f"Task variant: {configuration.get('task_variant', 'viscosity')}. "
               f"Model: {configuration['model']}; reasoning: {configuration['reasoning_effort']}; "
               f"output-token limit per response: {configuration['max_output_tokens']}.", ""]
    if manifest["mode"] == "dry-run":
        report += ["This is a scripted harness test, not a GPT-5.6 Sol result. API token counts and costs below are synthetic fixtures; actual API spending was $0.", ""]
    report += ["One instance and a simple fixed policy cannot establish adaptive-allocation gains or benchmark validity. "
               "The comparison has its own 20-credit ledger and identical target/noise stream; its result was never shown to the agent.", ""]
    if finished:
        evaluation, baseline = finished["evaluation"], finished.get("fixed_policy")
        report += ["| Run | Normalized forecast RMSE | Scientific credits spent |", "|---|---:|---:|"]
        for title, result in (("Agent" if manifest["mode"] == "live" else "Scripted fake", evaluation), ("Fixed policy", baseline)):
            if result is None:
                continue
            score = result.get("score")
            metric = "Not submitted" if score is None else f"{score['normalized_profile_rmse']:.10g}"
            spent = sum(result["scientific_budget"]["spent"].values())
            report.append(f"| {title} | {metric} | {spent:.10g} |")
        if baseline is not None:
            report += ["", "Fixed policy: " + baseline.get("description", "See the saved fixed-policy evaluation."), ""]
        report += ["", "## API accounting", "", "Conservative standard-pricing bounds, not an invoice. Unknown usage retains its full reservation. "
                   "Reasoning is included in output tokens; cache writes are covered by the input bound.", "",
                   "```json", json_text(finished["api_budget"]), "```", "",
                   "## Complete evaluation", "", "```json", json_text(evaluation), "```", "",
                   "Fixed-policy numerical details: [fixed_policy_evaluation.json](fixed_policy_evaluation.json).", ""]
        _write(path / "evaluation.json", json_text({"mode": manifest["mode"], **{k: finished[k] for k in
               ("termination_reason", "evaluation", "fixed_policy", "api_budget", "model_responses", "elapsed_seconds")}}) + "\n")
    else:
        last_budget = next((e["budget"] for e in reversed(events) if e["kind"] == "api_budget"), None)
        report += ["No finalized evaluation was recorded. No score has been reconstructed by rerunning the tools.", "",
                   "Last saved API ledger:", "", "```json", json_text(last_budget), "```", ""]
    report += ["## Local records", "", "- [Readable transcript](transcript.md)", "- [Chronological authoritative log](events.jsonl)",
               "- [Manifest, including separately marked PRIVATE harness configuration](manifest.json)",
               "- [Frozen tool definitions](tools.json)", "", "Raw records are private, local and untracked. Review before sharing.", ""]
    _write(path / "report.md", "\n".join(report))
    return path / "transcript.md", path / "report.md"
