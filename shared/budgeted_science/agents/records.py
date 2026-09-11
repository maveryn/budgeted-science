"""Durable, secret-scrubbed audit records. No automatic run cleanup or overwrite."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from uuid import uuid4


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def json_text(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


class Redactor:
    def __init__(self, secrets=()):
        self._secrets = set(secrets)

    def add(self, secret):
        if secret:
            self._secrets.add(secret)

    def clean(self, value):
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                if key.lower().replace("-", "_") in {"authorization", "api_key", "apikey", "access_token", "headers", "secret"}:
                    result[key] = "[REDACTED]"
                elif key == "encrypted_content" and isinstance(item, str):
                    # Opaque ciphertext can coincidentally contain key-like
                    # substrings. Do not pattern-scrub or decode it. Actual known
                    # plaintext credentials are still never written.
                    for secret in self._secrets:
                        item = item.replace(secret, "[REDACTED]")
                    result[key] = item
                else:
                    result[key] = self.clean(item)
            return result
        if isinstance(value, (list, tuple)):
            return [self.clean(v) for v in value]
        if isinstance(value, str):
            for secret in self._secrets:
                value = value.replace(secret, "[REDACTED]")
            value = re.sub(r"\bsk-[A-Za-z0-9_.*-]+", "[REDACTED]", value)
            return re.sub(r"(?i)Bearer\s+[^\s\"']+", "Bearer [REDACTED]", value)
        return value

    def error(self, exc):
        # Authentication errors may quote fragments not matching a full key.
        status = getattr(exc, "status_code", None)
        message = "Authentication/permission failure; credential details omitted." if status in (401, 403) else str(exc)
        return self.clean({"class": type(exc).__name__, "message": message,
                           "status_code": status, "request_id": getattr(exc, "request_id", None)})


class RunLog:
    def __init__(self, root, mode, redactor=None):
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{mode}-{uuid4().hex[:10]}"
        self.path = root / name
        self.path.mkdir(exist_ok=False)
        self.redactor = redactor if redactor is not None else Redactor()
        self._sequence = 0
        self._stream = (self.path / "events.jsonl").open("x", encoding="utf-8")

    def event(self, kind, **data):
        record = self.redactor.clean({"sequence": self._sequence + 1, "utc": utc_now(), "kind": kind, **data})
        serialized = json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n"
        self._stream.write(serialized)
        self._sequence += 1
        self._stream.flush()
        return record

    def write_json(self, relative, value, *, replace=False):
        target = (self.path / relative).resolve()
        if not target.is_relative_to(self.path.resolve()):
            raise ValueError("artifact must stay inside its run")
        target.parent.mkdir(parents=True, exist_ok=True)
        data = json_text(self.redactor.clean(value)) + "\n"
        if not replace:
            with target.open("x", encoding="utf-8") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        else:
            temporary = target.with_name(target.name + "." + uuid4().hex + ".tmp")
            with temporary.open("x", encoding="utf-8") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        return target.relative_to(self.path.resolve()).as_posix()

    def close(self):
        if not self._stream.closed:
            self._stream.flush()
            os.fsync(self._stream.fileno())
            self._stream.close()


def read_events(path):
    """A torn last line is recoverable; corruption in the middle is not hidden."""
    lines = (Path(path) / "events.jsonl").read_bytes().splitlines()
    records, torn_tail = [], False
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            record = json.loads(line.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            if i != len(lines) - 1:
                raise ValueError("corrupt event log before final line") from None
            torn_tail = True
            break
        if record.get("sequence") != len(records) + 1:
            raise ValueError("event sequence is not contiguous")
        records.append(record)
    return records, torn_tail
