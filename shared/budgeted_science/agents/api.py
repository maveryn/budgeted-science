"""Optional live Responses adapter. Importing this module never loads a key."""

from pathlib import Path
import re


def load_api_key(path):
    """Accept one plain key or a single OPENAI_API_KEY assignment; never echo input."""
    try:
        content = Path(path).read_text(encoding="utf-8-sig").strip()
    except OSError:
        raise ValueError("Cannot read the specified credential file.") from None
    keys = re.findall(r"\bsk-[A-Za-z0-9_-]+", content)
    if len(keys) != 1:
        raise ValueError("Credential file must contain exactly one unambiguous API key.")
    key = keys[0]
    remainder = content.replace(key, "").strip(" \r\n\t\"'")
    if remainder not in ("", "OPENAI_API_KEY=", "OPENAI_API_KEY ="):
        raise ValueError("Use a plain key or one OPENAI_API_KEY assignment, without other content.")
    return key


def count_payload(body):
    # Every context-bearing option in our generation payload is supported by
    # /responses/input_tokens. No local token estimate is used in live mode.
    keys = ("model", "input", "tools", "parallel_tool_calls", "reasoning", "truncation")
    return {key: body[key] for key in keys}


class OpenAIGateway:
    def __init__(self, api_key, *, http_client=None):
        from openai import AsyncOpenAI  # Optional dependency: live mode only.
        self.client = AsyncOpenAI(api_key=api_key, base_url="https://api.openai.com/v1",
                                  max_retries=0, timeout=120.0, http_client=http_client)

    async def count(self, body, metadata):
        raw = await self.client.responses.input_tokens.with_raw_response.count(**body)
        metadata({"request_id": raw.headers.get("x-request-id")})
        return raw.parse().model_dump(mode="json")

    async def stream(self, body, metadata):
        stream = await self.client.responses.create(**body)
        metadata({"request_id": stream.response.headers.get("x-request-id")})
        try:
            async for event in stream:
                yield event.model_dump(mode="json")
        finally:
            await stream.close()

    async def close(self):
        await self.client.close()
