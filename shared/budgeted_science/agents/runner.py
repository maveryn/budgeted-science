"""Single-episode orchestration. No retry, compaction, implicit live call or resume."""

import asyncio
from copy import deepcopy
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import subprocess
import time

from .api import OpenAIGateway, count_payload, load_api_key
from .config import PrivateInstance, RunConfig
from .fake import ScriptedGateway
from .planning import PlanningEpisode, prompts, run_fixed_policy, tool_definitions
from .records import RunLog, digest, utc_now
from .reporting import regenerate
from .spending import AccountingUnavailable, ApiBudget, ApiLimit, PRICING


class StopEpisode(Exception):
    pass


def provenance(repo):
    files = sorted((repo / "shared" / "budgeted_science").rglob("*.py"))
    files += [repo / "pyproject.toml", *sorted((repo / "demos/planning/src").glob("run*agent.py"))]
    files += sorted((repo / "tests").glob("test*.py"))
    hashes = {p.relative_to(repo).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in files if p.is_file()}
    versions = {"python": platform.python_version()}
    for name in ("numpy", "scipy", "openai", "httpx", "budgeted-science"):
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = "not installed"
    try:
        git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True,
                                           stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        git_head = None
    return {"dependencies": versions, "source_hashes": hashes, "source_manifest_hash": digest(hashes), "git_head": git_head}


def generation_body(config, history, tools):
    return {"model": config.model, "reasoning": {"effort": config.reasoning_effort, "summary": "auto"},
            "input": deepcopy(history), "tools": deepcopy(tools), "parallel_tool_calls": False,
            "max_output_tokens": config.max_output_tokens, "service_tier": "default",
            "store": False, "stream": True, "truncation": "disabled",
            "include": ["reasoning.encrypted_content"]}


def replay_output_item(item):
    """Project a returned item onto its API input form.

    The full returned object remains in the response archive. Returned status,
    null placeholders and server item IDs on messages are response metadata, not
    part of the manually managed semantic history. Reasoning IDs and encrypted
    content are retained so stateless reasoning can continue.
    """
    if not isinstance(item, dict):
        raise StopEpisode("malformed_model_output_item")
    kind = item.get("type")
    if kind == "reasoning":
        required = ("type", "id", "summary")
        optional = ("content", "encrypted_content")
    elif kind == "function_call":
        required = ("type", "call_id", "name", "arguments")
        optional = ("id", "caller", "namespace")
    elif kind == "message":
        required = ("type", "role", "content")
        optional = ("phase",)
    else:
        raise StopEpisode("unsupported_output_item")
    if any(key not in item or item[key] is None for key in required):
        raise StopEpisode("malformed_model_output_item")
    return deepcopy({key: item[key] for key in (*required, *optional)
                     if key in item and item[key] is not None})


async def run_episode(repo, output_root, *, mode, config=None, instance=None, gateway=None, key_file=None,
                      adapter=None):
    if mode not in ("dry-run", "live"):
        raise ValueError("Choose dry-run or explicitly choose live.")
    config = config or RunConfig()
    instance = instance or PrivateInstance(target_amplitude=1.1 if config.task_variant == "viscosity_amplitude" else 1.0)
    if adapter is None and config.task_variant == "viscosity" and instance.target_amplitude != 1.0:
        raise ValueError("one-parameter task requires target amplitude 1")
    repo = Path(repo).resolve()
    log = RunLog(output_root, mode)
    started = time.monotonic()
    episode = None
    render = regenerate if adapter is None else adapter.regenerate
    if adapter is None:
        messages, tools = prompts(config), tool_definitions(config)
    else:
        episode = adapter.create_episode(config, instance, log, started + config.deadline_seconds)
        messages, tools = adapter.prompts(config, episode), adapter.tool_definitions()
    manifest = {"schema_version": 1, "run_id": log.path.name, "mode": mode,
                "started_utc": utc_now(), "termination_reason": "running",
                "public_configuration": config.public(),
                "api_policy": {"endpoint": "https://api.openai.com/v1/responses", "stream": True,
                               "store": False, "service_tier": "default", "generation_retries": 0,
                               "parallel_tool_calls": False, "truncation": "disabled",
                               "reasoning": {"effort": "high", "summary": "auto"},
                               "include": ["reasoning.encrypted_content"]},
                "PRIVATE_harness_instance_not_agent_input": instance.private(),
                "pricing": PRICING, "prompt_hash": digest(messages), "tool_schema_hash": digest(tools),
                **provenance(repo)}
    log.write_json("manifest.json", manifest)
    log.write_json("prompts.json", messages)
    log.write_json("tools.json", tools)
    log.event("prompt_frozen", messages=messages, tool_schema_hash=digest(tools))
    log.event("run_started", mode=mode)
    money = ApiBudget(config.api_ceiling_usd)
    episode = episode if episode is not None else PlanningEpisode(config, instance, log)
    baseline, reason, responses = None, "internal_error", 0
    history = deepcopy(messages)
    history_output_sequences = []

    def remaining():
        value = config.deadline_seconds - (time.monotonic() - started)
        if value <= 0:
            raise StopEpisode("deadline")
        return value

    async def consume(body, request_id):
        final = None
        async for event in gateway.stream(body, lambda meta: log.event("api_metadata", local_request_id=request_id, **meta)):
            log.event("api_stream_event", request_id=request_id, event=event)
            if event.get("type") in ("response.completed", "response.incomplete", "response.failed"):
                if final is not None:
                    raise StopEpisode("multiple_terminal_responses")
                final = event["response"]
                artifact = log.write_json(f"api/{request_id}-response.json", final)
                log.event("api_response", request_id=request_id, response=final, artifact=artifact)
            elif event.get("type") == "error":
                raise StopEpisode("api_stream_error")
        if final is None:
            raise StopEpisode("stream_ended_without_response")
        return final

    try:
        # The paired comparison is an independent CPU run, never model context.
        baseline = (run_fixed_policy(config, instance, log) if adapter is None
                    else adapter.run_comparisons(config, instance, log))
        if adapter is not None:
            # CPU comparisons have their own limits, outside the agent deadline.
            started = time.monotonic()
            episode.deadline = started + config.deadline_seconds
            log.event("agent_started", deadline_seconds=config.deadline_seconds)
        remaining()
        if gateway is None:
            if mode == "dry-run":
                gateway = ScriptedGateway() if adapter is None else adapter.scripted_gateway()
            else:
                key = load_api_key(key_file or repo / "openaiapi.txt")
                log.redactor.add(key)
                gateway = OpenAIGateway(key)
                del key
        for index in range(1, config.max_responses + 1):
            remaining()
            request_id = f"generation-{index:03d}"
            body = generation_body(config, history, tools)
            count_body = count_payload(body)
            artifact = log.write_json(f"api/{request_id}-count-request.json", count_body)
            log.event("token_count_requested", request_id=request_id, artifact=artifact)
            try:
                count_timeout = remaining()
                count = await asyncio.wait_for(gateway.count(count_body, lambda meta:
                    log.event("count_metadata", local_request_id=request_id, **meta)), timeout=count_timeout)
                artifact = log.write_json(f"api/{request_id}-count-response.json", count)
                log.event("token_count_received", request_id=request_id, response=count, artifact=artifact)
                if count.get("object") != "response.input_tokens":
                    raise AccountingUnavailable("invalid_token_count_response")
                money.reserve(request_id, count["input_tokens"], config.max_output_tokens)
            except (asyncio.TimeoutError, StopEpisode, ApiLimit, AccountingUnavailable):
                raise
            except Exception as exc:
                log.event("run_error", stage="token_count", error=log.redactor.error(exc))
                raise StopEpisode("token_count_unavailable") from exc
            log.event("api_budget", request_id=request_id, budget=money.status())
            artifact = log.write_json(f"api/{request_id}-request.json", body)
            log.event("api_request_sent", request_id=request_id, artifact=artifact,
                      tool_output_sequences=list(history_output_sequences))
            responses += 1
            try:
                response_timeout = remaining()
                response = await asyncio.wait_for(consume(body, request_id), timeout=response_timeout)
            except BaseException:
                # Once attempted, a generation may be billed even without a
                # completed response. Its reservation is never silently released.
                log.event("api_usage_unknown", request_id=request_id, budget=money.status())
                raise
            try:
                money.settle(request_id, response.get("usage"))
            finally:
                log.event("api_budget", request_id=request_id, budget=money.status())
            if response.get("status") != "completed":
                raise StopEpisode("model_output_incomplete" if response.get("status") == "incomplete" else "api_response_failed")
            if response.get("model") != config.model or response.get("service_tier") != "default":
                raise StopEpisode("unexpected_model_or_service_tier")
            output = response.get("output")
            if not isinstance(output, list):
                raise StopEpisode("malformed_model_output")
            if any(c.get("type") == "refusal" for item in output for c in item.get("content", [])):
                raise StopEpisode("refusal")
            # Preserve every replayable output item (including opaque reasoning
            # and assistant phase), followed by function results in order. Full
            # returned objects remain unchanged in the raw response archive.
            history.extend(replay_output_item(item) for item in output)
            calls = [item for item in output if item.get("type") == "function_call"]
            if not calls:
                raise StopEpisode("no_submission")
            for call in calls:
                remaining()
                if call.get("status") not in (None, "completed"):
                    raise StopEpisode("incomplete_tool_call")
                if not all(isinstance(call.get(key), str) for key in ("call_id", "name", "arguments")):
                    raise StopEpisode("malformed_tool_call")
                result = episode.execute(call["call_id"], call["name"], call["arguments"])
                history_output_sequences.append(log._sequence)
                history.append({"type": "function_call_output", "call_id": call["call_id"],
                                "output": json.dumps(result, ensure_ascii=False, allow_nan=False)})
                if episode.submission is not None:
                    reason = "submitted"
                    break
            if reason == "submitted":
                break
        else:
            reason = "response_limit"
    except (StopEpisode, ApiLimit, AccountingUnavailable) as exc:
        reason = str(exc)
        log.event("interruption", reason=reason)
    except asyncio.TimeoutError:
        reason = "deadline"
        log.event("interruption", reason=reason)
    except (asyncio.CancelledError, KeyboardInterrupt):
        reason = "interrupted"
        log.event("interruption", reason=reason)
    except Exception as exc:
        reason = "request_or_runner_error"
        log.event("run_error", error=log.redactor.error(exc))
    finally:
        if gateway is not None:
            try:
                await asyncio.wait_for(gateway.close(), timeout=2.0)
            except Exception as exc:
                log.event("run_error", stage="client_close", error=log.redactor.error(exc))
        evaluation = episode.evaluate()
        log.event("run_finished", termination_reason=reason, evaluation=evaluation,
                  fixed_policy=baseline, api_budget=money.status(), model_responses=responses,
                  elapsed_seconds=time.monotonic() - started)
        manifest.update(termination_reason=reason, ended_utc=utc_now())
        log.write_json("manifest.json", manifest, replace=True)
        log.close()
        render(log.path)
    return log.path, reason
