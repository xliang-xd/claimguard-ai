from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Protocol
from uuid import uuid4


_SENSITIVE_FIELD_FRAGMENTS = (
    "api_key",
    "authorization",
    "credential",
    "token",
    "secret",
)
_RAW_MESSAGE_FIELDS = {
    "history",
    "messages",
    "conversation",
    "transcript",
    "input_items",
    "message",
    "content",
}


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    tenant_id: str
    session_id: str
    user_id: str
    details: dict[str, object]

    def __post_init__(self) -> None:
        _validate_audit_details(self.details)

    def validate(self) -> None:
        _validate_audit_details(self.details)


class AuditSink(Protocol):
    def record(self, event: AuditEvent) -> str: ...


class InMemoryAuditSink:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def record(self, event: AuditEvent) -> str:
        _validate_audit_details(event.details)
        self.events.append(event)
        return f"audit-{len(self.events):06d}"


class JsonlAuditSink:
    def __init__(self, path: Path):
        self._path = path

    def record(self, event: AuditEvent) -> str:
        _validate_audit_details(event.details)
        audit_id = f"audit-{uuid4().hex}"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "audit_id": audit_id,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            **asdict(event),
        }
        with self._path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return audit_id


def _validate_audit_details(value: object) -> None:
    if isinstance(value, Mapping):
        normalized_keys = {
            key.casefold() for key in value if isinstance(key, str)
        }
        if {"role", "content"}.issubset(normalized_keys):
            raise ValueError("raw customer message details are not allowed")
        for key, nested_value in value.items():
            _validate_audit_key(key)
            _validate_audit_details(nested_value)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _validate_audit_details(item)


def _validate_audit_key(key: object) -> None:
    if not isinstance(key, str):
        return
    normalized_key = key.casefold()
    if any(fragment in normalized_key for fragment in _SENSITIVE_FIELD_FRAGMENTS):
        raise ValueError("sensitive audit field is not allowed")
    if normalized_key in _RAW_MESSAGE_FIELDS or normalized_key.endswith("_message"):
        raise ValueError("raw customer message details are not allowed")
