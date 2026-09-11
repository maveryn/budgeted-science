"""Scripted offline gateway; no credentials, network, or model inference."""
import json
import re
from .fake import ScriptedGateway


class VerificationGateway(ScriptedGateway):
    def __init__(self, fail_turn=None):
        super().__init__()
        self.fail_turn = fail_turn

    async def stream(self, body, metadata):
        self.requests.append(body)
        previous = [i for i in body["input"] if i.get("type") == "function_call_output"]
        turn = len(previous) + 1
        yield {"type": "response.created", "response": {"id": f"fake-{turn}", "status": "in_progress"}}
        if len(self.requests) == self.fail_turn:
            raise OSError("synthetic interrupted stream")
        if not previous:
            public = next(i["content"] for i in body["input"] if i.get("role") == "user")
            original = re.search(r'"run_id": "(run-[a-z0-9]+)"', public).group(1)
            name, args = "refine_integration", {"run_id": original}
        else:
            last = json.loads(previous[-1]["output"])["result"]
            if turn == 2:
                name, args = "refine_sampling", {"run_id": last["run_id"]}
            else:
                name, args = "submit", {"verdict": "ACCEPT", "diagnosis": "Offline fixture only.",
                                       "evidence_ids": [last["run_id"]],
                                       "justification": "Predetermined offline response, not model performance."}
        output = [
            {"type": "reasoning", "id": f"reason-{turn}", "encrypted_content": "opaque-fixture",
             "summary": [{"type": "summary_text", "text": "Scripted test summary."}]},
            {"type": "message", "role": "assistant", "phase": "commentary",
             "content": [{"type": "output_text", "text": f"Offline fixture: {name}."}]},
            {"type": "function_call", "call_id": f"fake-call-{turn}", "name": name,
             "arguments": json.dumps(args), "status": "completed"}]
        metadata({"request_id": f"offline-{turn}"})
        yield {"type": "response.completed", "response": {
            "id": f"fake-{turn}", "status": "completed", "model": body["model"],
            "service_tier": "default", "output": output,
            "usage": {"input_tokens": self.input_tokens, "output_tokens": 100,
                      "input_tokens_details": {"cached_tokens": 0},
                      "output_tokens_details": {"reasoning_tokens": 20}}}}
