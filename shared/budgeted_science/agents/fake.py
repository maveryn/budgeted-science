"""Scripted, explicitly non-LLM model for offline end-to-end verification."""

import json


class ScriptedGateway:
    def __init__(self):
        self.requests = []
        self.input_tokens = 0

    async def count(self, body, metadata):
        # Synthetic accounting fixtures only, never a substitute for live count.
        self.input_tokens = len(json.dumps(body).encode())
        metadata({"request_id": "fake-count"})
        return {"object": "response.input_tokens", "input_tokens": self.input_tokens}

    async def stream(self, body, metadata):
        self.requests.append(body)
        turn = len(self.requests)
        metadata({"request_id": f"fake-request-{turn}"})
        previous = [item for item in body["input"] if item.get("type") == "function_call_output"]
        last = json.loads(previous[-1]["output"])["result"] if previous else None
        if turn == 1:
            name, args = "observe", {"sensor_id": 2, "replicates": 1}
        elif turn == 2:
            name, args = "fit", {"record_ids": [last[0]["record_id"]], "resolution": 32, "max_evaluations": 16}
        elif turn == 3:
            name, args = "simulate", {"viscosity": last["viscosity"], "resolution": 64, "protocol": "forecast"}
        else:
            name, args = "submit", {"profile": last["forecast_profile"]}
        output = [
            {"type": "reasoning", "id": f"fake-reason-{turn}",
             "summary": [{"type": "summary_text", "text": f"Scripted dry-run step {turn}; not model reasoning."}],
             "encrypted_content": "opaque-offline-fixture"},
            {"type": "message", "id": f"fake-message-{turn}", "role": "assistant", "status": "completed",
             "phase": "commentary", "content": [{"type": "output_text", "text": f"Offline action: {name}.", "annotations": []}]},
            {"type": "function_call", "id": f"fake-tool-{turn}", "call_id": f"fake-call-{turn}",
             "name": name, "arguments": json.dumps(args), "status": "completed"},
        ]
        yield {"type": "response.created", "response": {"id": f"fake-response-{turn}", "status": "in_progress"}}
        yield {"type": "response.output_text.delta", "delta": f"Offline action: {name}."}
        response = {"id": f"fake-response-{turn}", "object": "response", "status": "completed",
                    "model": body["model"], "service_tier": "default", "output": output,
                    "usage": {"input_tokens": self.input_tokens, "output_tokens": 100,
                              "total_tokens": self.input_tokens + 100,
                              "input_tokens_details": {"cached_tokens": 0},
                              "output_tokens_details": {"reasoning_tokens": 20}}}
        yield {"type": "response.completed", "response": response}

    async def close(self):
        pass
