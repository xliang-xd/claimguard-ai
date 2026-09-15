from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal, Protocol

from agents import Agent, RunConfig, Runner

from claimguard.agent_runtime.agents import CopilotAgentOutput, CopilotAgents
from claimguard.agent_runtime.audit import AuditEvent
from claimguard.agent_runtime.state import CopilotContext, ConversationState, SessionStore


_SAFE_AUDIT_ID = re.compile(r"[A-Za-z0-9_-]+")


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
    ):
        self._agents = agents
        self._run_config = run_config
        self._session_store = session_store
        self._runner = runner or SDKAgentRunner()

    async def run_turn(
        self,
        context: CopilotContext,
        message: str,
    ) -> CopilotTurnResult:
        try:
            state = self._session_store.load(context.tenant_id, context.session_id)
            starting_agent, agent_input = self._resume_turn(state, context, message)
            result = await self._runner.run(
                starting_agent,
                agent_input,
                context=context,
                run_config=self._run_config,
            )
            output = self._validated_output(result.final_output)
            last_agent_name = self._validated_last_agent_name(result.last_agent.name)
            input_items = self._validated_input_items(result.to_input_list())
            self._session_store.save(
                ConversationState(
                    tenant_id=context.tenant_id,
                    session_id=context.session_id,
                    user_id=context.user_id,
                    current_agent=last_agent_name,
                    input_items=input_items,
                )
            )
            audit_id = self._record(
                context,
                "run_completed",
                {"current_agent": last_agent_name, "outcome": output.status},
            )
            if not audit_id:
                return self._failed_result(context)
            return CopilotTurnResult(
                status=output.status,
                session_id=context.session_id,
                current_agent=last_agent_name,
                draft=output.draft,
                audit_id=audit_id,
            )
        except Exception:
            return self._failed_result(context)

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

    def _failed_result(self, context: CopilotContext) -> CopilotTurnResult:
        return CopilotTurnResult(
            status="human_takeover",
            session_id=context.session_id,
            current_agent="Copilot Router Agent",
            draft="",
            audit_id=self._record(
                context,
                "run_failed",
                {"outcome": "human_takeover"},
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
