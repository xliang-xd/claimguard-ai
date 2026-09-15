from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from claimguard.agent_runtime.audit import AuditSink
from claimguard.embeddings import EmbeddingClient
from claimguard.knowledge import KnowledgeIndex


@dataclass(frozen=True)
class CopilotContext:
    tenant_id: str
    session_id: str
    user_id: str
    knowledge_index: KnowledgeIndex
    embedding_client: EmbeddingClient
    audit_sink: AuditSink


@dataclass(frozen=True)
class ConversationState:
    tenant_id: str
    session_id: str
    user_id: str
    current_agent: str
    input_items: tuple[dict[str, object], ...] = ()


class SessionStore(Protocol):
    def load(self, tenant_id: str, session_id: str) -> ConversationState | None: ...

    def save(self, state: ConversationState) -> None: ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._states: dict[tuple[str, str], ConversationState] = {}

    def load(self, tenant_id: str, session_id: str) -> ConversationState | None:
        return self._states.get(_session_key(tenant_id, session_id))

    def save(self, state: ConversationState) -> None:
        self._states[_session_key(state.tenant_id, state.session_id)] = state


def _session_key(tenant_id: str, session_id: str) -> tuple[str, str]:
    _validate_identifier(tenant_id, "tenant_id")
    _validate_identifier(session_id, "session_id")
    return tenant_id, session_id


def _validate_identifier(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty")
