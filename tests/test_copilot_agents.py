from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock

from agents import AgentOutputSchema, custom_span, trace
from agents.exceptions import ModelBehaviorError
from agents.run import get_output_schema
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.agent_runtime.agents import (
    CopilotAgentOutput,
    build_copilot_agents,
)
from claimguard.agent_runtime.settings import AgentRuntimeSettings


def agent_settings() -> AgentRuntimeSettings:
    return AgentRuntimeSettings(
        api_key="test-key",
        base_url="https://workspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        router_model="qwen3.8-flash",
        policy_model="qwen3.7-plus",
        openai_tracing_enabled=False,
    )


class CopilotAgentsTest(unittest.TestCase):
    def test_router_can_only_handoff_to_policy_in_v0_5(self):
        tool = MagicMock(name="policy_search_tool")

        agents = build_copilot_agents(agent_settings(), tool)

        self.assertEqual(agents.router.name, "Copilot Router Agent")
        self.assertEqual(agents.policy.name, "Policy Agent")
        self.assertEqual(
            [handoff.agent_name for handoff in agents.router.handoffs],
            ["Policy Agent"],
        )
        self.assertEqual(agents.router.tools, [])
        self.assertEqual(agents.policy.tools, [agents.policy_search_tool])
        self.assertEqual(agents.policy.handoffs, [])
        self.assertEqual(
            agents.by_name,
            {
                "Copilot Router Agent": agents.router,
                "Policy Agent": agents.policy,
            },
        )
        self.assertIs(agents.router.output_type, CopilotAgentOutput)
        self.assertIs(agents.policy.output_type, CopilotAgentOutput)
        tool.assert_not_called()

    def test_models_are_explicit_per_agent(self):
        agents = build_copilot_agents(
            agent_settings(),
            MagicMock(name="policy_search_tool"),
        )

        self.assertEqual(agents.router.model, "qwen3.8-flash")
        self.assertEqual(agents.policy.model, "qwen3.7-plus")

    def test_instructions_require_evidence_based_safe_outputs(self):
        agents = build_copilot_agents(
            agent_settings(),
            MagicMock(name="policy_search_tool"),
        )

        self.assertIn("Policy Agent", agents.router.instructions)
        self.assertIn('status="human_takeover"', agents.router.instructions)
        self.assertIn('draft=""', agents.router.instructions)
        self.assertIn("先调用检索工具", agents.policy.instructions)
        self.assertIn("只根据检索工具返回的条款证据", agents.policy.instructions)
        self.assertIn('status="human_takeover"', agents.policy.instructions)
        self.assertIn('draft=""', agents.policy.instructions)
        self.assertIn('status="draft_ready"', agents.policy.instructions)
        self.assertIn("客服草稿", agents.policy.instructions)

    def test_output_contract_accepts_valid_state_combinations(self):
        draft = CopilotAgentOutput(status="draft_ready", draft="客服草稿：请参考条款")
        takeover = CopilotAgentOutput(status="human_takeover", draft="")

        self.assertEqual(draft.status, "draft_ready")
        self.assertEqual(draft.draft, "客服草稿：请参考条款")
        self.assertEqual(takeover.status, "human_takeover")
        self.assertEqual(takeover.draft, "")

    def test_output_contract_rejects_invalid_state_combinations(self):
        invalid_outputs = [
            {"status": "human_takeover", "draft": "客服草稿：请参考条款"},
            {"status": "draft_ready", "draft": ""},
            {"status": "draft_ready", "draft": "请参考条款"},
        ]

        for output in invalid_outputs:
            with self.subTest(output=output), self.assertRaises(ValidationError):
                CopilotAgentOutput(**output)

    def test_output_contract_rejects_unknown_status(self):
        with self.assertRaises(ValidationError):
            CopilotAgentOutput(status="unknown", draft="")

    def test_configured_agent_output_schema_enforces_state_contract_for_json(self):
        agents = build_copilot_agents(
            agent_settings(),
            MagicMock(name="policy_search_tool"),
        )
        output_schema = get_output_schema(agents.router)

        self.assertIsInstance(output_schema, AgentOutputSchema)

        invalid_payloads = [
            '{"status": "human_takeover", "draft": "客服草稿：请参考条款"}',
            '{"status": "draft_ready", "draft": "请参考条款"}',
        ]

        with trace("test", disabled=True):
            with custom_span("output_schema_validation"):
                for payload in invalid_payloads:
                    with self.subTest(payload=payload), self.assertRaises(
                        ModelBehaviorError
                    ):
                        output_schema.validate_json(payload)

                output = output_schema.validate_json(
                    '{"status": "draft_ready", "draft": "客服草稿：请参考条款"}'
                )

        self.assertIsInstance(output, CopilotAgentOutput)
        self.assertEqual(output.status, "draft_ready")
        self.assertEqual(output.draft, "客服草稿：请参考条款")


if __name__ == "__main__":
    unittest.main()
