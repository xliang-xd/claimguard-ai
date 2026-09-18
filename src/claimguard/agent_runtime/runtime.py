from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
import re
from typing import AsyncContextManager, Literal, Protocol

from agents import Agent, RunConfig, Runner

from claimguard.agent_runtime.agents import CopilotAgentOutput, CopilotAgents
from claimguard.agent_runtime.audit import AuditEvent
from claimguard.agent_runtime.state import CopilotContext, ConversationState, SessionStore
from claimguard.citation_judge import CitationJudge, CitationVerdict


_SAFE_AUDIT_ID = re.compile(r"[A-Za-z0-9_-]+")
_CITATION_REASON_CODES = {
    "supported": "citation_supported",
    "unsupported": "citation_unsupported",
    "insufficient_evidence": "insufficient_evidence",
}


class _UnknownCitationError(ValueError):
    pass


@dataclass(frozen=True)
class CopilotTurnResult:
    status: Literal["draft_ready", "human_takeover"]
    session_id: str
    current_agent: str
    draft: str
    audit_id: str


class AgentRunner(Protocol):
    async def run(
        self,
        starting_agent: Agent[CopilotContext],
        agent_input: str | list[dict[str, object]],
        *,
        context: CopilotContext,
        run_config: RunConfig,
    ) -> object: ...


class SDKAgentRunner:
    async def run(
        self,
        starting_agent: Agent[CopilotContext],
        agent_input: str | list[dict[str, object]],
        *,
        context: CopilotContext,
        run_config: RunConfig,
    ) -> object:
        return await Runner.run(
            starting_agent,
            agent_input,
            context=context,
            run_config=run_config,
            max_turns=6,
        )


class CopilotRuntime:
    def __init__(
        self,
        agents: CopilotAgents,
        run_config: RunConfig,
        session_store: SessionStore,
        runner: AgentRunner | None = None,
        citation_judge: CitationJudge | None = None,
    ):
        self._agents = agents
        self._run_config = run_config
        self._session_store = session_store
        self._runner = runner or SDKAgentRunner()
        self._citation_judge = citation_judge
        self._legacy_session_locks: dict[tuple[str, str], asyncio.Lock] = {}

    async def run_turn(
        self,
        context: CopilotContext,
        message: str,
    ) -> CopilotTurnResult:
        try:
            async with self._exclusive_session(context.tenant_id, context.session_id):
                context.evidence_ledger.clear()
                state = self._session_store.load(context.tenant_id, context.session_id)
                starting_agent, agent_input = self._resume_turn(state, context, message)
                result = await self._runner.run(
                    starting_agent,
                    agent_input,
                    context=context,
                    run_config=self._run_config,
                )
                try:
                    output = self._validated_output(result.final_output)
                    last_agent_name = self._validated_last_agent_name(result.last_agent.name)
                    input_items = self._validated_input_items(result.to_input_list())
                except Exception:
                    return self._failed_result(context, failure_category="invalid_output")
                if output.status != "draft_ready":
                    return self._failed_result(
                        context,
                        failure_category="agent_human_takeover",
                    )
                evidence = context.evidence_ledger.snapshot()
                if not evidence:
                    return self._failed_result(context, failure_category="no_evidence")
                if self._citation_judge is None:
                    return self._failed_result(context, failure_category="judge_unavailable")
                try:
                    verdict = self._citation_judge.judge(output.draft, evidence)
                    citation_status, citation_ids = self._validated_verdict(
                        verdict,
                        evidence,
                    )
                except _UnknownCitationError:
                    return self._failed_result(
                        context,
                        citation_status="supported",
                        failure_category="unknown_citation",
                    )
                except ValueError:
                    return self._failed_result(context, failure_category="invalid_verdict")
                except Exception:
                    return self._failed_result(context, failure_category="judge_error")
                if citation_status != "supported":
                    return self._failed_result(
                        context,
                        citation_status=citation_status,
                        failure_category="unsupported_verdict",
                    )
                next_state = ConversationState(
                    tenant_id=context.tenant_id,
                    session_id=context.session_id,
                    user_id=context.user_id,
                    current_agent=last_agent_name,
                    input_items=input_items,
                )
                audit_id = self._record(
                    context,
                    "run_completed",
                    {
                        "current_agent": last_agent_name,
                        "evidence_count": len(evidence),
                        "citation_status": citation_status,
                        "citation_ids": citation_ids,
                    },
                )
                if not audit_id:
                    return self._failed_result(
                        context,
                        citation_status=citation_status,
                        citation_ids=citation_ids,
                        failure_category="audit_failed",
                    )
                self._session_store.save(next_state)
                return CopilotTurnResult(
                    status=output.status,
                    session_id=context.session_id,
                    current_agent=last_agent_name,
                    draft=output.draft,
                    audit_id=audit_id,
                )
        except Exception:
            return self._failed_result(context, failure_category="runtime_error")

    def _exclusive_session(
        self,
        tenant_id: str,
        session_id: str,
    ) -> AsyncContextManager[None]:
        exclusive_session = getattr(self._session_store, "exclusive_session", None)
        if callable(exclusive_session):
            return exclusive_session(tenant_id, session_id)
        return self._legacy_exclusive_session(tenant_id, session_id)

    @asynccontextmanager
    async def _legacy_exclusive_session(self, tenant_id: str, session_id: str):
        """兼容仅实现 load/save 的旧 SessionStore。

        回退锁只在当前 CopilotRuntime 实例和事件循环内生效；多个 Runtime
        实例或事件循环共享旧 Store 时，不能保证 load-run-save 的会话串行化。
        这类 Store 应实现 exclusive_session 以获得跨运行时、跨事件循环的保证。
        """
        lock = self._legacy_session_locks.setdefault((tenant_id, session_id), asyncio.Lock())
        async with lock:
            yield

    def _resume_turn(
        self,
        state: ConversationState | None,
        context: CopilotContext,
        message: str,
    ) -> tuple[Agent[CopilotContext], str | list[dict[str, object]]]:
        if state is None:
            return self._agents.router, message
        if (
            state.tenant_id != context.tenant_id
            or state.session_id != context.session_id
            or state.user_id != context.user_id
        ):
            raise ValueError("invalid session identity")
        starting_agent = self._agents.by_name.get(state.current_agent)
        if starting_agent is None:
            raise ValueError("unknown session agent")
        return starting_agent, [*state.input_items, {"role": "user", "content": message}]

    def _validated_output(self, output: object) -> CopilotAgentOutput:
        if not isinstance(output, CopilotAgentOutput):
            raise ValueError("invalid agent output")
        if output.status == "human_takeover" and output.draft == "":
            return output
        if (
            output.status == "draft_ready"
            and isinstance(output.draft, str)
            and output.draft.startswith("客服草稿：")
        ):
            return output
        raise ValueError("invalid agent output")

    def _validated_last_agent_name(self, last_agent_name: object) -> str:
        if not isinstance(last_agent_name, str) or last_agent_name not in self._agents.by_name:
            raise ValueError("invalid last agent")
        return last_agent_name

    def _validated_input_items(
        self,
        input_items: object,
    ) -> tuple[dict[str, object], ...]:
        if not isinstance(input_items, list) or not all(
            isinstance(item, dict) for item in input_items
        ):
            raise ValueError("invalid input history")
        return tuple(input_items)

    @staticmethod
    def _validated_verdict(
        verdict: object,
        evidence: tuple[object, ...],
    ) -> tuple[str, tuple[str, ...]]:
        if not isinstance(verdict, CitationVerdict):
            raise ValueError("invalid citation verdict")
        if (
            verdict.status not in _CITATION_REASON_CODES
            or verdict.reason_code != _CITATION_REASON_CODES[verdict.status]
            or not isinstance(verdict.citations, tuple)
            or any(not isinstance(citation_id, str) for citation_id in verdict.citations)
        ):
            raise ValueError("invalid citation verdict")
        if verdict.status != "supported":
            if verdict.citations:
                raise ValueError("invalid citation verdict")
            return verdict.status, ()
        if not verdict.citations:
            raise ValueError("invalid citation verdict")
        evidence_ids = {record.clause_id for record in evidence}
        if any(citation_id not in evidence_ids for citation_id in verdict.citations):
            raise _UnknownCitationError
        return verdict.status, verdict.citations

    def _failed_result(
        self,
        context: CopilotContext,
        *,
        failure_category: str,
        citation_status: str = "not_judged",
        citation_ids: tuple[str, ...] = (),
    ) -> CopilotTurnResult:
        return CopilotTurnResult(
            status="human_takeover",
            session_id=context.session_id,
            current_agent="Copilot Router Agent",
            draft="",
            audit_id=self._record(
                context,
                "citation_failed",
                {
                    "citation_status": citation_status,
                    "citation_ids": citation_ids,
                    "failure_category": failure_category,
                },
            ),
        )

    @staticmethod
    def _record(
        context: CopilotContext,
        event_type: str,
        details: dict[str, object],
    ) -> str:
        try:
            audit_id = context.audit_sink.record(
                AuditEvent(
                    event_type=event_type,
                    tenant_id=context.tenant_id,
                    session_id=context.session_id,
                    user_id=context.user_id,
                    details=details,
                )
            )
        except Exception:
            return ""
        return audit_id if isinstance(audit_id, str) and _SAFE_AUDIT_ID.fullmatch(audit_id) else ""
