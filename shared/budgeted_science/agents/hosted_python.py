"""Explicit, network-disabled hosted Python container and conservative accounting.

Importing this module does not import the SDK, load credentials, or use a network.
"""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import re

from .api import OpenAIGateway
from .records import json_text
from .runner import StopEpisode, replay_output_item
from .spending import AccountingUnavailable, ApiLimit

MODEL = "gpt-5.6-luna"
MAX_OUTPUT = 32768
MAX_TOOL_CALLS = 1
# A built-in call may incur another model pass within one Responses request.
# Reserve both passes at the model's maximum input size and long-context rates;
# the input-count endpoint alone cannot bound subsequent tool-generated input.
MAX_BILLED_INPUT = 922000 * (MAX_TOOL_CALLS + 1)
CONTAINER_RESERVE = Decimal("0.09")
REQUEST_RESERVE = (Decimal(MAX_BILLED_INPUT)*Decimal("0.50")
                   + Decimal(MAX_OUTPUT)*Decimal("1.80"))/1_000_000


class HostedBudget:
    def __init__(self, live=True):
        self.live, self.container_attempted = live, False
        self.known, self.pending, self.measured = Decimal(0), {}, []

    def start_container(self):
        if self.container_attempted:
            raise ApiLimit("container_already_attempted")
        self.container_attempted = True

    def reserve(self, request_id, count):
        if type(count) is not int or not 0 <= count <= 256000:
            raise AccountingUnavailable("invalid_or_excessive_input_count")
        if request_id in self.pending or any(r["request_id"] == request_id for r in self.measured):
            raise AccountingUnavailable("duplicate_generation")
        if self.committed + REQUEST_RESERVE > Decimal("2.00"):
            raise ApiLimit("api_ceiling")
        self.pending[request_id] = REQUEST_RESERVE

    @property
    def committed(self):
        return self.known + sum(self.pending.values(), Decimal(0)) + (
            CONTAINER_RESERVE if self.container_attempted else Decimal(0))

    def settle(self, request_id, usage):
        if request_id not in self.pending:
            raise AccountingUnavailable("unreserved_generation")
        try:
            inputs, outputs = usage["input_tokens"], usage["output_tokens"]
            cached = (usage.get("input_tokens_details") or {}).get("cached_tokens", 0)
            reasoning = (usage.get("output_tokens_details") or {}).get("reasoning_tokens", 0)
            if any(type(v) is not int or v < 0 for v in (inputs, outputs, cached, reasoning)):
                raise ValueError()
            if cached > inputs or reasoning > outputs:
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            raise AccountingUnavailable("missing_or_invalid_usage") from None
        # Aggregated usage cannot reveal the length of every internal model pass.
        # Use long-context/cache-write rates for the conservative measured bound.
        upper = (Decimal(inputs)*Decimal("0.50") + Decimal(outputs)*Decimal("1.80"))/1_000_000
        lower = (Decimal(inputs-cached)*Decimal("0.20") + Decimal(cached)*Decimal("0.02")
                 + Decimal(outputs)*Decimal("1.20"))/1_000_000
        self.measured.append({"request_id": request_id, "usage": usage,
            "standard_cost_lower_usd": str(lower), "conservative_cost_upper_usd": str(upper)})
        self.known += upper
        del self.pending[request_id]
        if inputs > MAX_BILLED_INPUT or outputs > MAX_OUTPUT or self.committed > 2:
            raise AccountingUnavailable("usage_exceeded_reservation")

    def status(self):
        return {"ceiling_usd": "2.00", "known_model_upper_usd": str(self.known),
            "unknown_model_reserved_usd": str(sum(self.pending.values(), Decimal(0))),
            "container_upper_reserved_usd": str(CONTAINER_RESERVE if self.container_attempted else 0),
            "committed_upper_usd": str(self.committed), "measured_responses": deepcopy(self.measured),
            "unsettled_requests": list(self.pending), "is_invoice": False,
            "actual_api_usd": None if self.live else 0}


def replay_hosted(item, container_id):
    if item.get("type") != "code_interpreter_call":
        return replay_output_item(item)
    fields = ("id", "code", "container_id", "outputs", "status", "type")
    if (any(k not in item for k in fields) or item["container_id"] != container_id
            or item["status"] not in ("completed", "failed", "incomplete", "interpreting", "in_progress")):
        raise StopEpisode("invalid_hosted_tool_output")
    # code and outputs are REQUIRED nullable fields in the installed input schema.
    return deepcopy({key: item[key] for key in fields})


def hosted_activity(output):
    """A final response may retain a nonterminal item for an over-limit attempt.

    Count terminal executions, not every emitted call item. Preserve nonterminal
    items unchanged in history; never invent their outputs or run their code.
    """
    items = [item for item in output if item.get("type") == "code_interpreter_call"]
    terminal = [item for item in items if item.get("status") in ("completed", "failed", "incomplete")]
    pending = [item for item in items if item.get("status") in ("interpreting", "in_progress")]
    if len(terminal) > MAX_TOOL_CALLS:
        raise StopEpisode("hosted_tool_limit_violation")
    return items, terminal, pending


class HostedGateway(OpenAIGateway):
    def __init__(self, key, log, *, http_client=None):
        super().__init__(key, http_client=http_client)
        self.log, self.container_id, self.uploaded = log, None, {}

    async def start(self):
        body = {"name": self.log.path.name, "memory_limit": "1g",
                "network_policy": {"type": "disabled"},
                "expires_after": {"anchor": "last_active_at", "minutes": 20}}
        self.log.write_json("container/create-request.json", body)
        self.log.event("container_create_requested", body=body)
        raw = await self.client.containers.with_raw_response.create(**body)
        result = raw.parse().model_dump(mode="json")
        self.container_id = result["id"]
        self.log.write_json("container/create-response.json", result)
        self.log.event("container_created", result=result, request_id=raw.headers.get("x-request-id"))
        if result.get("memory_limit") != "1g":
            raise StopEpisode("unexpected_container_memory")
        if (result.get("network_policy") or {}).get("type") != "disabled":
            raise StopEpisode("container_network_policy_unconfirmed")
        return self.container_id

    async def upload(self, filename, value):
        """Caller passes an allowlisted public value, never an arbitrary local path."""
        payload = (json_text(value)+"\n").encode("utf-8")
        sha = hashlib.sha256(payload).hexdigest()
        key = (filename, sha)
        if key in self.uploaded:
            return deepcopy(self.uploaded[key])
        if not re.fullmatch(r"[A-Za-z0-9_.-]+\.json", filename) or len(payload) > 5_000_000:
            raise ValueError("invalid or oversized public upload")
        self.log.write_json(f"uploads/{sha}.json", value)
        self.log.event("container_upload_requested", filename=filename, sha256=sha, bytes=len(payload))
        raw = await self.client.containers.files.with_raw_response.create(
            self.container_id, file=(filename, payload, "application/json"))
        result = raw.parse().model_dump(mode="json")
        if result.get("container_id") != self.container_id:
            raise StopEpisode("unexpected_upload_container")
        self.log.event("container_upload_completed", result=result, sha256=sha,
                       request_id=raw.headers.get("x-request-id"))
        pointer = {"container_id": self.container_id, "file_id": result["id"],
                   "path": result["path"], "sha256": sha, "bytes": len(payload)}
        self.uploaded[key] = pointer
        return deepcopy(pointer)

    async def finish(self):
        """Archive files as inert bytes, then delete this run's ephemeral container."""
        if not self.container_id:
            return
        try:
            total, count = 0, 0
            async for item in self.client.containers.files.list(self.container_id):
                meta = item.model_dump(mode="json")
                count += 1
                total += meta["bytes"]
                self.log.event("container_file_found", file=meta)
                if count > 100 or total > 20_000_000:
                    self.log.event("container_archive_incomplete", reason="artifact safety size/count cap")
                    break
                response = await self.client.containers.files.content.retrieve(
                    meta["id"], container_id=self.container_id)
                data = response.content
                # Never use provider/model filenames as host paths or execute them.
                sha = hashlib.sha256(data).hexdigest()
                path = self.log.path / "container" / "files" / (sha+".bin")
                path.parent.mkdir(parents=True, exist_ok=True)
                if not path.exists():
                    with path.open("xb") as stream:
                        stream.write(data)
                self.log.event("container_file_archived", file=meta, sha256=sha,
                               artifact=path.relative_to(self.log.path).as_posix())
        finally:
            self.log.event("container_delete_requested", container_id=self.container_id)
            await self.client.containers.delete(self.container_id)
            self.log.event("container_deleted", container_id=self.container_id)


class FakeHostedGateway:
    """Scripted transport fixture. Does not execute Python or contact any service."""
    def __init__(self):
        self.container_id = "cntr_offline"
        self.index, self.requests = 0, []

    async def start(self):
        return self.container_id

    async def upload(self, filename, value):
        return {"container_id": self.container_id, "file_id": "offline-"+filename,
                "path": "/mnt/data/"+filename}

    async def count(self, body, metadata):
        return {"object": "response.input_tokens", "input_tokens": 10000}

    async def stream(self, body, metadata):
        self.requests.append(deepcopy(body))
        self.index += 1
        if self.index == 1:
            output = [{"id": "ci_fixture", "type": "code_interpreter_call",
                       "container_id": self.container_id, "code": "print('offline fixture')",
                       "outputs": [{"type": "logs", "logs": "offline fixture"}], "status": "completed"},
                      {"id": "rs_fixture", "type": "reasoning", "summary": [],
                       "encrypted_content": "opaque_fixture"}]
        else:
            output = [{"id": "fc_fixture", "call_id": "fake-submit", "type": "function_call",
                       "name": "submit", "arguments": json.dumps({"verdict": "ABSTAIN",
                       "diagnosis": "Scripted fixture", "evidence_ids": [],
                       "justification": "No live code or agent was evaluated."})}]
        yield {"type": "response.output_item.added", "item": output[0]}
        yield {"type": "response.completed", "response": {"id": f"resp_{self.index}",
               "model": MODEL, "service_tier": "default", "status": "completed", "output": output,
               "usage": {"input_tokens": 10000, "output_tokens": 100}}}

    async def finish(self):
        pass

    async def close(self):
        pass
