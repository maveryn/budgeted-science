"""Scripted offline integration fixture; never a substitute for live token counting."""

import json

from .fake import ScriptedGateway


class ResourceScriptedGateway(ScriptedGateway):
    async def stream(self, body, metadata):
        self.requests.append(body)
        turn = len(self.requests)
        metadata({"request_id": f"resource-fake-{turn}"})
        previous = [item for item in body["input"] if item.get("type") == "function_call_output"]
        if turn == 1:
            name, arguments = "simulate_low", {"theta": [1.0, .08, 1.4]}
        elif turn == 2:
            name, arguments = "measure_target", {"variable": "y", "time": 4.0}
        elif turn == 3:
            name, arguments = "simulate_high", {"theta": [.95, .085, 1.5]}
        elif turn == 4:
            name, arguments = "fit_purchased", {}
        else:
            last = json.loads(previous[-1]["output"])
            name, arguments = "submit", {"theta_hat": last["result"]["posterior_mean"]}
        response = {
            "id": f"resource-fake-response-{turn}", "object": "response", "status": "completed",
            "model": body["model"], "service_tier": "default", "output": [
                {"type": "reasoning", "id": f"reason-{turn}", "summary": [
                    {"type": "summary_text", "text": "Scripted offline step; not model reasoning."}],
                 "encrypted_content": "opaque-offline-fixture"},
                {"type": "message", "id": f"message-{turn}", "role": "assistant", "phase": "commentary",
                 "status": "completed", "content": [
                     {"type": "output_text", "text": f"Offline action: {name}.", "annotations": []}]},
                {"type": "function_call", "id": f"tool-{turn}", "call_id": f"call-{turn}",
                 "name": name, "arguments": json.dumps(arguments), "status": "completed"}],
            "usage": {"input_tokens": self.input_tokens, "output_tokens": 100,
                      "total_tokens": self.input_tokens + 100,
                      "input_tokens_details": {"cached_tokens": 0},
                      "output_tokens_details": {"reasoning_tokens": 20}}}
        yield {"type": "response.created", "response": {"id": response["id"], "status": "in_progress"}}
        yield {"type": "response.output_text.delta", "delta": f"Offline action: {name}."}
        yield {"type": "response.completed", "response": response}
