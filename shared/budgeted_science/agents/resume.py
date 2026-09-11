"""Explicit, fail-closed resource-episode continuation from local audit records."""

from copy import deepcopy
from dataclasses import fields
from datetime import datetime
from decimal import Decimal
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import shutil

from budgeted_science.resource_planning.checkpoint import restore_episode
from budgeted_science.resource_planning.environment import _SOLVER_KEY
from .records import digest, read_events
from .resource import ResourceInstance, ResourceRunConfig, tool_definitions
from .spending import ApiBudget


def read_json(parent, relative):
    path = (parent / relative).resolve()
    if not path.is_relative_to(parent.resolve()):
        raise ValueError("saved artifact escapes run directory")
    return json.loads(path.read_text(encoding="utf-8"))


def save_checkpoint(log, episode):
    if not hasattr(episode, "checkpoint"):
        return
    payload = episode.checkpoint()
    log.write_json("checkpoint.json", {"last_sequence": log._sequence,
                                      "payload_hash": digest(payload), "payload": payload}, replace=True)


def legacy_state(parent, events, final):
    """Migrate the first finalized run, which predates explicit checkpoints."""
    if final is None:
        raise ValueError("legacy runs require finalized state; ambiguous interrupted tools cannot be replayed")
    start = next(e["data"] for e in events if e["kind"] == "environment_event"
                 and e["role"] == "agent" and e["event_kind"] == "episode_started")
    status = final["evaluation"]["scientific_status"]
    observations = {(r["variable"], r["time"]): deepcopy(r) for r in start["observations"]}
    simulations, executed, requested, fits = {}, {}, {}, {}
    for event in events:
        if event["kind"] == "tool_requested" and event["role"] == "agent":
            requested[event["call_id"]] = [event["name"], event["arguments"]]
        elif event["kind"] == "tool_result" and event["role"] == "agent":
            call_id = event["call_id"]
            if call_id not in requested:
                raise ValueError("tool result has no matching request")
            executed.setdefault(call_id, [digest(requested[call_id]), deepcopy(event["output"])])
        elif event["kind"] == "fit_finished" and event["role"] == "agent":
            fits[event["evidence_hash"]] = deepcopy(event["result"])
        elif event["kind"] == "environment_event" and event["role"] == "agent":
            data = event["data"]
            if event["event_kind"] == "simulation":
                result = data["result"]
                if result["result_id"] not in simulations:
                    if result["status"] == "success" and not data.get("artifact_path"):
                        raise ValueError("missing purchased trajectory artifact")
                    simulations[result["result_id"]] = {
                        **{k: result[k] for k in ("theta", "fidelity", "charge", "remaining", "status", "result_id")},
                        "baseline_values": result["values"],
                        "trajectory": read_json(parent, data["artifact_path"]) if result["status"] == "success" else None}
            elif event["event_kind"] == "measurement":
                result = data["result"]
                observations.setdefault((result["variable"], result["time"]), deepcopy(result))
    if set(requested) != set(executed):
        raise ValueError("unfinished tool execution requires manual audit; it will not be repeated")
    state = {"version": 1, "solver_key": list(_SOLVER_KEY), "config": start["config"],
             "theta_true": start["theta_true"], "target": read_json(parent, start["private_reference_artifact"]),
             "state": status["status"], "submission": status["submission"],
             "ledger": status["ledger"], "observations": list(observations.values()),
             "cache": list(simulations.values())}
    if restore_episode(state).tools.get_status() != status:
        raise ValueError("legacy restored state disagrees with saved final scientific status")
    return {"environment": state, "executed": executed, "fits": fits,
            "initial_observations": start["observations"]}


def prepare_resume(parent, *, mode, require_full_budget=False, api_ceiling_usd=None):
    """Read and validate everything before creating a continuation or using a key."""
    from .runner import replay_output_item
    parent = Path(parent).resolve()
    manifest = read_json(parent, "manifest.json")
    if manifest.get("termination_reason") in (None, "running"):
        raise ValueError("attempt is active or did not finalize; audit it before resuming")
    if manifest["mode"] != mode:
        raise ValueError("dry/live mode cannot change across a continuation")
    if (parent / "resume_claim.json").exists():
        raise ValueError("this attempt already has a continuation; resume its child instead")
    public = manifest["public_configuration"]
    if public.get("task_variant") != "resource_planning":
        raise ValueError("resume currently supports the predator-prey resource task only")
    names = {f.name for f in fields(ResourceRunConfig)}
    values = {k: v for k, v in public.items() if k in names}
    values["require_full_budget"] = require_full_budget or public.get("require_full_budget", False)
    if api_ceiling_usd is not None:
        amount = Decimal(api_ceiling_usd)
        if not amount.is_finite() or not Decimal(public["api_ceiling_usd"]) <= amount <= 3:
            raise ValueError("explicit resume ceiling must not decrease and cannot exceed $3")
        values["api_ceiling_usd"] = str(amount)
    config = ResourceRunConfig(**values)
    if public["environment"] != config.public()["environment"] or public["fit_settings"] != config.public()["fit_settings"]:
        raise ValueError("scientific configuration changed; cannot resume")
    for name in ("numpy", "scipy"):
        if manifest["dependencies"][name] != version(name):
            raise ValueError("numerical dependency version changed; cannot resume")
    repo = Path(__file__).resolve().parents[3]
    for relative in ("shared/budgeted_science/resource_planning/environment.py",
                     "shared/budgeted_science/resource_planning/emulator.py",
                     "shared/budgeted_science/resource_planning/policies.py",
                     "shared/budgeted_science/resource_planning/config.py"):
        if hashlib.sha256((repo / relative).read_bytes()).hexdigest() != manifest["source_hashes"][relative]:
            raise ValueError("scientific implementation changed; cannot resume")
    messages, tools = read_json(parent, "prompts.json"), read_json(parent, "tools.json")
    if digest(messages) != manifest["prompt_hash"] or digest(tools) != manifest["tool_schema_hash"]:
        raise ValueError("frozen prompt or schema changed")
    if digest(tools) != digest(tool_definitions(config)):
        raise ValueError("tool schema migration is not supported")
    events, torn = read_events(parent)
    if torn:
        raise ValueError("torn event log requires manual audit; original preserved")
    final = next((e for e in reversed(events) if e["kind"] == "run_finished"), None)
    if final and final["evaluation"].get("valid"):
        raise ValueError("a submitted episode cannot be resumed")
    if (parent / "checkpoint.json").is_file():
        checkpoint = read_json(parent, "checkpoint.json")
        saved = checkpoint["payload"]
        if digest(saved) != checkpoint["payload_hash"] or checkpoint["last_sequence"] > len(events):
            raise ValueError("invalid checkpoint checksum or journal position")
        if any(e["sequence"] > checkpoint["last_sequence"] and e["kind"] == "tool_requested"
               and e["role"] == "agent" for e in events):
            raise ValueError("uncheckpointed tool execution requires manual audit")
    else:
        saved = legacy_state(parent, events, final)
    restored = restore_episode(saved["environment"])
    if final and restored.tools.get_status() != final["evaluation"]["scientific_status"]:
        raise ValueError("checkpoint disagrees with finalized state")
    private = manifest["PRIVATE_harness_instance_not_agent_input"]
    instance = ResourceInstance(tuple(private["target_parameters"]), private["target_seed"], private.get("noise_seed", 0))
    if tuple(saved["environment"]["theta_true"]) != instance.theta:
        raise ValueError("private target mismatch")
    if (restored.tools.public_config != config.environment_config().public()
            or restored._noise_seed != instance.noise_seed):
        raise ValueError("saved environment or noise stream mismatch")
    history, output_sequences, pending = deepcopy(messages), [], {}
    attempted, ids, requested = 0, [], set()
    for event in events:
        kind = event["kind"]
        if kind == "resume_started":
            history.append(deepcopy(event["message"]))
        elif kind == "token_count_requested":
            ids.append(int(event["request_id"].split("-")[-1]))
        elif kind == "api_request_sent":
            attempted += 1
        elif kind == "api_response" and event["response"].get("status") == "completed":
            response = event["response"]
            if response.get("model") != config.model or response.get("service_tier") != "default":
                raise ValueError("previous response used unexpected model or tier")
            for item in response["output"]:
                history.append(replay_output_item(item))
                if item["type"] == "function_call":
                    pending[item["call_id"]] = item
        elif kind == "tool_requested" and event["role"] == "agent":
            requested.add(event["call_id"])
        elif kind == "tool_result" and event["role"] == "agent":
            if event["call_id"] not in pending:
                raise ValueError("tool result is not matched to model history")
            pending.pop(event["call_id"])
            history.append({"type": "function_call_output", "call_id": event["call_id"],
                            "output": json.dumps(event["output"], ensure_ascii=False, allow_nan=False)})
            output_sequences.append(event["sequence"])
    if pending:
        raise ValueError("unexecuted completed-response tools require a separate recovery audit; no duplicate work attempted")
    status = final["api_budget"] if final else next(e["budget"] for e in reversed(events) if e["kind"] == "api_budget")
    reservations = {}
    for name in status["unsettled_requests"]:
        count = read_json(parent, f"api/{name}-count-response.json")
        # Counting may complete before the generation file is durably written.
        body_path = parent / f"api/{name}-request.json"
        limit = read_json(parent, body_path.relative_to(parent))["max_output_tokens"] if body_path.exists() else config.max_output_tokens
        reservations[name] = {"input_tokens": count["input_tokens"], "max_output_tokens": limit}
    money = ApiBudget.restore(status, reservations)
    if money.ceiling != Decimal(public["api_ceiling_usd"]):
        raise ValueError("saved API ceiling disagrees with manifest")
    # Only an explicit caller override may raise the cumulative ceiling. All
    # measured usage and unsettled reservations remain exactly as restored.
    money.ceiling = Decimal(config.api_ceiling_usd)
    if final:
        elapsed = final["elapsed_seconds"]
        comparisons = final["fixed_policy"]
    else:
        start = next(e for e in reversed(events) if e["kind"] == "agent_started")
        elapsed = (datetime.fromisoformat(events[-1]["utc"]) - datetime.fromisoformat(start["utc"])).total_seconds()
        elapsed += manifest.get("resume", {}).get("prior_elapsed_seconds", 0)
        comparisons = {p: read_json(parent, f"comparisons/{p}.json") for p in ("random", "adaptive")}
    if attempted >= config.max_responses or elapsed >= config.deadline_seconds:
        raise ValueError("original response or active-time limit has been exhausted")
    remaining = restored.tools.get_status()["remaining"]
    content = (f"Continue this same interrupted episode. Existing purchases and conversation are retained. "
               f"You have {remaining:g} of the original {config.scientific_budget:g} scientific credits remaining. "
               f"There are {config.max_responses - attempted} model responses left under the original limits. "
               "Do not start over; use the evidence and free analysis tools already available. ")
    if config.require_full_budget:
        content += (f"The user now requires the FULL {config.scientific_budget:g}-credit scientific budget to be used before submission. "
                    "Choose useful additional purchases yourself; a submit call is rejected while credits remain. ")
    content += (f"The cumulative API ceiling is ${config.api_ceiling_usd}, including all prior usage "
                "and interrupted request reservations; this is not a new allowance. ")
    if config.api_ceiling_usd != public["api_ceiling_usd"]:
        content += (f"The user explicitly authorized increasing the total ceiling from "
                    f"${public['api_ceiling_usd']} to ${config.api_ceiling_usd}. ")
    if remaining == 0:
        content += "Scientific purchases are complete. Finish your estimate using the purchased evidence and free tools, then submit."
    message = {"role": "user", "content": content}
    history.append(message)
    return {"parent": parent, "manifest": manifest, "events": events, "config": config, "instance": instance,
            "saved": saved, "history": history, "messages": messages, "tools": tools,
            "output_sequences": output_sequences, "money": money, "responses": attempted,
            "next_generation": max(ids, default=0) + 1, "elapsed": elapsed,
            "comparisons": comparisons, "message": message}


def inherit_run(log, resume):
    """A fresh child contains immutable copies of the earlier audit trail."""
    parent = resume["parent"]
    if log.path.resolve().is_relative_to(parent):
        raise ValueError("continuation directory must be outside its parent attempt")
    # An exclusive permanent marker prevents duplicate child spending. Continue
    # a failed child, never fork the same parent's remaining budget twice.
    with (parent / "resume_claim.json").open("x", encoding="utf-8") as stream:
        json.dump({"child": str(log.path.resolve()), "parent": str(parent)}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    log.close()
    previous = log.path / "prior_attempts" / parent.name
    previous.mkdir(parents=True)
    for name in ("manifest.json", "report.md", "transcript.md", "evaluation.json", "checkpoint.json"):
        if (parent / name).is_file():
            shutil.copy2(parent / name, previous / name)
    for name in ("api", "numerical", "private", "fitting", "comparisons", "prior_attempts"):
        if (parent / name).is_dir():
            for path in (parent / name).rglob("*"):
                if not path.resolve().is_relative_to(parent) or path.is_symlink():
                    raise ValueError("linked artifacts are not supported")
            shutil.copytree(parent / name, log.path / name, dirs_exist_ok=True)
    for name in ("events.jsonl", "prompts.json", "tools.json"):
        shutil.copy2(parent / name, log.path / name)
    log._stream = (log.path / "events.jsonl").open("a", encoding="utf-8")
    log._sequence = len(resume["events"])
    log.event("resume_started", parent=str(parent), parent_run_id=parent.name,
              message=resume["message"], prior_responses=resume["responses"],
              prior_elapsed_seconds=resume["elapsed"], api_budget=resume["money"].status())
