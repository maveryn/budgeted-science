"""Explicit continuation of finalized, unsubmitted verification attempts."""
from copy import deepcopy
from decimal import Decimal
import hashlib
from importlib.metadata import version
import json
from pathlib import Path

from .records import digest, read_events
from .resume import read_json
from .spending import ApiBudget, pricing_for_model
from .verification import VerificationConfig, VerificationInstance, VerificationEpisode, tool_definitions


def prepare_resume(parent, *, mode, config_type=VerificationConfig, instance_type=VerificationInstance,
                   episode_type=VerificationEpisode, definitions=tool_definitions):
    from .runner import replay_output_item
    parent = Path(parent).resolve()
    manifest = read_json(parent, "manifest.json")
    if manifest.get("termination_reason") in (None, "running"):
        raise ValueError("active/unfinalized attempt requires manual audit")
    if manifest["mode"] != mode or (parent / "resume_claim.json").exists():
        raise ValueError("mode changed or this attempt already has a continuation")
    config = config_type(**manifest["public_configuration"])
    if manifest["pricing"] != pricing_for_model(config.model):
        raise ValueError("pricing changed")
    for name in ("numpy", "scipy"):
        if manifest["dependencies"][name] != version(name):
            raise ValueError("numerical dependency changed")
    repo = Path(__file__).resolve().parents[3]
    for relative, expected in manifest["source_hashes"].items():
        if ("/claim_verification/" in relative or "/claim_verification_incremental/" in relative
                or relative.startswith("shared/budgeted_science/agents/")
                or relative.endswith("resource_planning/environment.py")):
            if hashlib.sha256((repo / relative).read_bytes()).hexdigest() != expected:
                raise ValueError("saved implementation changed; resume requires review")
    messages, tools = read_json(parent, "prompts.json"), read_json(parent, "tools.json")
    if (digest(messages) != manifest["prompt_hash"] or digest(tools) != manifest["tool_schema_hash"]
            or tools != definitions(config)):
        raise ValueError("frozen prompt or tools changed")
    study = read_json(parent, "private/verification-study.json")
    private = manifest["PRIVATE_harness_instance_not_agent_input"]
    if digest(study) != private["study_hash"] or study["case_id"] != private["case_id"]:
        raise ValueError("private case identity changed")
    instance = instance_type(study, private["catalog_path"], private["catalog_digest"], private["selection"])
    events, torn = read_events(parent)
    if torn:
        raise ValueError("torn event log requires manual audit")
    final = next((e for e in reversed(events) if e["kind"] == "run_finished"), None)
    if not final or final["evaluation"]["valid_submission"]:
        raise ValueError("only durably finalized, unsubmitted attempts can resume")
    checkpoint = read_json(parent, "checkpoint.json")
    saved = checkpoint["payload"]
    if digest(saved) != checkpoint["payload_hash"] or checkpoint["last_sequence"] > len(events):
        raise ValueError("checkpoint integrity failed")
    if any(e["sequence"] > checkpoint["last_sequence"] and e["kind"] == "tool_requested"
           and e.get("role") == "agent" for e in events):
        raise ValueError("uncheckpointed tool execution cannot be repeated")
    # Restoration performs validation but no solver calls or writes.
    restored = episode_type.restore(config, instance, None, None, saved)
    if restored.budget_status() != final["evaluation"]["scientific_status"]:
        raise ValueError("checkpoint and final budget disagree")
    if saved["request_count"] >= config.max_tool_requests:
        raise ValueError("tool request limit exhausted")
    history, output_sequences, pending, ids = deepcopy(messages), [], {}, []
    attempted = 0
    for e in events:
        if e["kind"] == "resume_started":
            history.append(deepcopy(e["message"]))
        elif e["kind"] == "token_count_requested":
            ids.append(int(e["request_id"].split("-")[-1]))
        elif e["kind"] == "api_request_sent":
            attempted += 1
        elif e["kind"] == "api_response" and e["response"].get("status") == "completed":
            response = e["response"]
            if response.get("model") != config.model or response.get("service_tier") != "default":
                raise ValueError("unexpected prior model or tier")
            for item in response["output"]:
                history.append(replay_output_item(item))
                if item["type"] == "function_call":
                    pending[item["call_id"]] = item
        elif e["kind"] == "tool_result" and e.get("role") == "agent":
            if e["call_id"] not in pending:
                raise ValueError("unmatched tool result")
            pending.pop(e["call_id"])
            history.append({"type": "function_call_output", "call_id": e["call_id"],
                            "output": json.dumps(e["output"], ensure_ascii=False, allow_nan=False)})
            output_sequences.append(e["sequence"])
    if pending:
        raise ValueError("pending completed-response actions require manual audit")
    status, reservations = final["api_budget"], {}
    for name in status["unsettled_requests"]:
        count = read_json(parent, f"api/{name}-count-response.json")
        body = parent / f"api/{name}-request.json"
        limit = read_json(parent, body.relative_to(parent))["max_output_tokens"] if body.exists() else config.max_output_tokens
        reservations[name] = {"input_tokens": count["input_tokens"], "max_output_tokens": limit}
    money = ApiBudget.restore(status, reservations, model=config.model)
    if money.ceiling != Decimal(config.api_ceiling_usd):
        raise ValueError("API ceiling mismatch")
    elapsed = final["elapsed_seconds"]
    if attempted >= config.max_responses or elapsed >= config.deadline_seconds:
        raise ValueError("original response or active-time limit exhausted")
    message = {"role": "user", "content":
               f"Continue the SAME interrupted audit with its purchased evidence and history. "
               f"Remaining audit credits: {restored.environment.remaining:g} of {config.scientific_budget}. "
               f"Cumulative API ceiling remains USD {config.api_ceiling_usd}, including earlier "
               "usage and uncertain reservations. Do not repurchase or start over. "
               "Submission is allowed at any spend; there is no full-budget requirement."}
    history.append(message)
    return {"parent": parent, "manifest": manifest, "events": events, "config": config,
            "instance": instance, "saved": saved, "history": history, "messages": messages,
            "tools": tools, "output_sequences": output_sequences, "money": money,
            "responses": attempted, "next_generation": max(ids, default=0) + 1,
            "elapsed": elapsed, "comparisons": final["fixed_policy"], "message": message}
