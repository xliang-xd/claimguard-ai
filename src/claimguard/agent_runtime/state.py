from __future__ import annotations

import asyncio
from collections import deque
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


class ExclusiveSessionStore(SessionStore, Protocol):
    def exclusive_session(
        self,
        tenant_id: str,
        session_id: str,
    ) -> AsyncContextManager[None]: ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._states: dict[tuple[str, str], ConversationState] = {}
        self._session_locks: dict[tuple[str, str], _SessionGate] = {}
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
            gate = self._session_locks.setdefault(session_key, _SessionGate())
        return _SessionCriticalSection(gate)


class _SessionGate:
    """将同一会话的等待者移交到各自的事件循环，不占用默认线程池。"""

    def __init__(self) -> None:
        self._guard = Lock()
        self._held = False
        self._waiters: deque[_SessionWaiter] = deque()

    async def acquire(self) -> None:
        loop = asyncio.get_running_loop()
        waiter = _SessionWaiter(loop.create_future(), loop)
        with self._guard:
            if not self._held:
                self._held = True
                return
            self._waiters.append(waiter)
        try:
            await asyncio.shield(waiter.future)
        except BaseException:
            with self._guard:
                granted = waiter.granted
                waiter.active = False
            if granted:
                self.release()
            raise

    def release(self) -> None:
        with self._guard:
            while self._waiters:
                waiter = self._waiters.popleft()
                if waiter.active:
                    waiter.granted = True
                    break
            else:
                self._held = False
                return
        try:
            waiter.loop.call_soon_threadsafe(_wake_waiter, waiter)
        except RuntimeError:
            with self._guard:
                waiter.active = False
            self.release()


@dataclass
class _SessionWaiter:
    future: asyncio.Future[None]
    loop: asyncio.AbstractEventLoop
    active: bool = True
    granted: bool = False


def _wake_waiter(waiter: _SessionWaiter) -> None:
    if not waiter.future.done():
        waiter.future.set_result(None)


class _SessionCriticalSection:
    def __init__(self, gate: _SessionGate) -> None:
        self._gate = gate
        self._acquired = False

    async def __aenter__(self) -> None:
        await self._gate.acquire()
        self._acquired = True

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        if self._acquired:
            self._gate.release()


def _session_key(tenant_id: str, session_id: str) -> tuple[str, str]:
    _validate_identifier(tenant_id, "tenant_id")
    _validate_identifier(session_id, "session_id")
    return tenant_id, session_id


def _validate_identifier(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty")
