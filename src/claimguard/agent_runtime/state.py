from __future__ import annotations

import asyncio
from _thread import LockType
from dataclasses import dataclass
from threading import Lock
from typing import AsyncContextManager, Protocol

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

    def exclusive_session(
        self,
        tenant_id: str,
        session_id: str,
    ) -> AsyncContextManager[None]: ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._states: dict[tuple[str, str], ConversationState] = {}
        self._session_locks: dict[tuple[str, str], LockType] = {}
        self._session_locks_guard = Lock()

    def load(self, tenant_id: str, session_id: str) -> ConversationState | None:
        return self._states.get(_session_key(tenant_id, session_id))

    def save(self, state: ConversationState) -> None:
        self._states[_session_key(state.tenant_id, state.session_id)] = state

    def exclusive_session(
        self,
        tenant_id: str,
        session_id: str,
    ) -> AsyncContextManager[None]:
        session_key = _session_key(tenant_id, session_id)
        with self._session_locks_guard:
            lock = self._session_locks.setdefault(session_key, Lock())
        return _SessionCriticalSection(lock)


class _SessionCriticalSection:
    def __init__(self, lock: LockType) -> None:
        self._lock = lock
        self._acquired = False

    async def __aenter__(self) -> None:
        acquire_task = asyncio.create_task(asyncio.to_thread(self._lock.acquire))
        try:
            await asyncio.shield(acquire_task)
        except BaseException:
            acquire_task.add_done_callback(self._release_after_cancelled_acquire)
            raise
        self._acquired = True

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        if self._acquired:
            self._lock.release()

    def _release_after_cancelled_acquire(self, acquire_task) -> None:
        if acquire_task.cancelled():
            return
        try:
            acquire_task.result()
        except BaseException:
            return
        self._lock.release()


def _session_key(tenant_id: str, session_id: str) -> tuple[str, str]:
    _validate_identifier(tenant_id, "tenant_id")
    _validate_identifier(session_id, "session_id")
    return tenant_id, session_id


def _validate_identifier(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty")
