from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from agents import Agent, FunctionTool, handoff
from pydantic import BaseModel, model_validator

from claimguard.agent_runtime.settings import AgentRuntimeSettings
from claimguard.agent_runtime.state import CopilotContext


ROUTER_INSTRUCTIONS = """
你是保险客服 Copilot 的路由 Agent。你只负责识别意图和执行 Handoff，不回答复杂的保险问题。

当用户询问保险条款、保障责任、等待期、免责或其他保单解释问题时，必须 Handoff 给 Policy Agent。
当前只允许 Handoff 给 Policy Agent；不得尝试转交给 Claims、Complaint 或其他 Agent。

对于无法识别的意图，或不属于保险条款解释的问题，直接返回结构化输出：
status="human_takeover"，draft=""。
状态必须通过结构化输出的 status 字段返回，不要用自然语言文本表达状态。
""".strip()


POLICY_INSTRUCTIONS = """
你是 Policy Agent，负责起草保险条款解释的客服回复。

回答前必须先调用检索工具获取当前问题的条款证据。只根据检索工具返回的条款证据，
不得补充、猜测或编造未检索到的条款、保障结论或赔付承诺。

如果没有证据、证据不足，或问题无法依据返回条款回答，返回结构化输出：
status="human_takeover"，draft=""。
如果证据足够，返回结构化输出：status="draft_ready"；draft 必须以“客服草稿：”明确标识，
并且只说明检索到的条款证据支持的内容。
状态必须通过结构化输出的 status 字段返回，不要用自然语言文本表达状态。
""".strip()


class CopilotAgentOutput(BaseModel):
    status: Literal["draft_ready", "human_takeover"]
    draft: str

    @model_validator(mode="after")
    def validate_state(self) -> CopilotAgentOutput:
        if self.status == "human_takeover" and self.draft != "":
            raise ValueError("human_takeover requires an empty draft")
        if self.status == "draft_ready" and not self.draft.startswith("客服草稿："):
            raise ValueError("draft_ready requires a customer-service draft")
        return self


@dataclass(frozen=True)
class CopilotAgents:
    router: Agent[CopilotContext]
    policy: Agent[CopilotContext]
    policy_search_tool: FunctionTool

    @property
    def by_name(self) -> dict[str, Agent[CopilotContext]]:
        return {self.router.name: self.router, self.policy.name: self.policy}


def build_copilot_agents(
    settings: AgentRuntimeSettings,
    policy_search_tool: FunctionTool,
) -> CopilotAgents:
    policy = Agent[CopilotContext](
        name="Policy Agent",
        model=settings.policy_model,
        instructions=POLICY_INSTRUCTIONS,
        tools=[policy_search_tool],
        output_type=CopilotAgentOutput,
    )
    router = Agent[CopilotContext](
        name="Copilot Router Agent",
        model=settings.router_model,
        instructions=ROUTER_INSTRUCTIONS,
        handoffs=[
            handoff(
                policy,
                tool_name_override="transfer_to_policy_agent",
                tool_description_override="将保险条款解释问题交给 Policy Agent。",
            )
        ],
        output_type=CopilotAgentOutput,
    )
    return CopilotAgents(router, policy, policy_search_tool)
