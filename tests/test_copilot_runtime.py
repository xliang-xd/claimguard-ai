from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.agent_runtime.agents import CopilotAgentOutput
from claimguard.agent_runtime.audit import InMemoryAuditSink
from claimguard.agent_runtime.runtime import CopilotRuntime, SDKAgentRunner
from claimguard.agent_runtime.state import (
    ConversationState,
    CopilotContext,
    InMemorySessionStore,
)


class ScriptedRunner:
    def __init__(self, last_agent_name, output, result_input_items=()):
        self.last_agent_name = last_agent_name
        self.output = output
        self.result_input_items = result_input_items
        self.starting_agent_names = []
        self.inputs = []

    async def run(self, starting_agent, agent_input, *, context, run_config):
        self.starting_agent_names.append(starting_agent.name)
        self.inputs.append(agent_input)
        return ScriptedRunResult(
            self.last_agent_name,
            self.output,
            self.result_input_items,
        )


class ScriptedRunResult:
    def __init__(self, last_agent_name, output, input_items):
        self.last_agent = SimpleNamespace(name=last_agent_name)
        self.final_output = output
        self._input_items = list(input_items)

    def to_input_list(self):
        return list(self._input_items)


class FailingRunner:
    async def run(self, starting_agent, agent_input, *, context, run_config):
        raise RuntimeError("Authorization: Bearer test-secret")


def make_context():
    return CopilotContext(
        tenant_id="tenant-a",
        session_id="session-1",
        user_id="agent-7",
        knowledge_index=MagicMock(),
        embedding_client=MagicMock(),
        audit_sink=InMemoryAuditSink(),
    )


def make_runtime(runner, store):
    router = SimpleNamespace(name="Copilot Router Agent")
    policy = SimpleNamespace(name="Policy Agent")
    agents = SimpleNamespace(
        router=router,
        by_name={router.name: router, policy.name: policy},
    )
    return CopilotRuntime(
        agents=agents,
        run_config=MagicMock(),
        session_store=store,
        runner=runner,
    )


class CopilotRuntimeTest(unittest.IsolatedAsyncioTestCase):
    async def test_starts_at_router_then_persists_last_agent(self):
        history = (
            {"role": "user", "content": "等待期是什么？"},
            {"role": "assistant", "content": "客服回复草稿"},
        )
        runner = ScriptedRunner(
            last_agent_name="Policy Agent",
            output=CopilotAgentOutput(
                status="draft_ready",
                draft="客服草稿：等待期说明",
            ),
            result_input_items=history,
        )
        store = InMemorySessionStore()
        runtime = make_runtime(runner=runner, store=store)

        context = make_context()
        result = await runtime.run_turn(context, "等待期是什么？")

        self.assertEqual(runner.starting_agent_names, ["Copilot Router Agent"])
        self.assertEqual(result.current_agent, "Policy Agent")
        self.assertEqual(result.status, "draft_ready")
        self.assertEqual(
            store.load("tenant-a", "session-1").current_agent,
            "Policy Agent",
        )
        self.assertEqual(store.load("tenant-a", "session-1").input_items, history)
        self.assertEqual(
            context.audit_sink.events[-1].details,
            {"current_agent": "Policy Agent", "outcome": "draft_ready"},
        )

    async def test_next_turn_resumes_at_last_agent(self):
        store = InMemorySessionStore()
        prior_history = (
            {"role": "user", "content": "等待期是什么？"},
            {"role": "assistant", "content": "客服回复草稿"},
        )
        store.save(
            ConversationState(
                "tenant-a",
                "session-1",
                "agent-7",
                "Policy Agent",
                prior_history,
            )
        )
        runner = ScriptedRunner(
            last_agent_name="Policy Agent",
            output=CopilotAgentOutput(status="draft_ready", draft="客服草稿：补充说明"),
        )
        runtime = make_runtime(runner=runner, store=store)

        await runtime.run_turn(make_context(), "那具体是几天？")

        self.assertEqual(runner.starting_agent_names, ["Policy Agent"])
        self.assertEqual(runner.inputs[0][:-1], list(prior_history))
        self.assertEqual(runner.inputs[0][-1]["content"], "那具体是几天？")

    async def test_model_error_fails_closed_without_disclosing_exception(self):
        context = make_context()
        runtime = make_runtime(FailingRunner(), InMemorySessionStore())

        result = await runtime.run_turn(context, "等待期是什么？")

        self.assertEqual(result.status, "human_takeover")
        self.assertEqual(result.draft, "")
        self.assertNotIn("test-secret", repr(result))
        self.assertEqual(context.audit_sink.events[-1].event_type, "run_failed")
        self.assertEqual(
            context.audit_sink.events[-1].details,
            {"outcome": "human_takeover"},
        )

    async def test_structured_human_takeover_is_preserved(self):
        runner = ScriptedRunner(
            last_agent_name="Copilot Router Agent",
            output=CopilotAgentOutput(status="human_takeover", draft=""),
        )
        runtime = make_runtime(runner, InMemorySessionStore())

        result = await runtime.run_turn(make_context(), "我有个复杂问题")

        self.assertEqual(result.status, "human_takeover")
        self.assertEqual(result.draft, "")

    async def test_mismatched_session_user_fails_closed_before_running(self):
        store = InMemorySessionStore()
        store.save(
            ConversationState(
                "tenant-a",
                "session-1",
                "another-user",
                "Policy Agent",
            )
        )
        runner = ScriptedRunner(
            last_agent_name="Policy Agent",
            output=CopilotAgentOutput(status="draft_ready", draft="客服草稿：不应运行"),
        )
        context = make_context()

        result = await make_runtime(runner, store).run_turn(context, "等待期是什么？")

        self.assertEqual(result.status, "human_takeover")
        self.assertEqual(result.draft, "")
        self.assertEqual(runner.starting_agent_names, [])
        self.assertEqual(context.audit_sink.events[-1].event_type, "run_failed")
        self.assertEqual(
            context.audit_sink.events[-1].details,
            {"outcome": "human_takeover"},
        )

    async def test_unknown_session_agent_fails_closed_without_disclosure(self):
        store = InMemorySessionStore()
        store.save(
            ConversationState(
                "tenant-a",
                "session-1",
                "agent-7",
                "Authorization: Bearer test-secret",
            )
        )
        runner = ScriptedRunner(
            last_agent_name="Policy Agent",
            output=CopilotAgentOutput(status="draft_ready", draft="客服草稿：不应运行"),
        )
        context = make_context()

        result = await make_runtime(runner, store).run_turn(context, "等待期是什么？")

        self.assertEqual(result.status, "human_takeover")
        self.assertEqual(result.draft, "")
        self.assertNotIn("test-secret", repr(result))
        self.assertEqual(runner.starting_agent_names, [])
        self.assertEqual(context.audit_sink.events[-1].event_type, "run_failed")
        self.assertEqual(
            context.audit_sink.events[-1].details,
            {"outcome": "human_takeover"},
        )

    async def test_invalid_output_fails_closed_without_recording_tool_contents(self):
        runner = ScriptedRunner(
            last_agent_name="Policy Agent",
            output={"tool_result": "Authorization: Bearer test-secret"},
        )
        context = make_context()

        result = await make_runtime(runner, InMemorySessionStore()).run_turn(
            context,
            "等待期是什么？",
        )

        self.assertEqual(result.status, "human_takeover")
        self.assertEqual(result.draft, "")
        self.assertNotIn("test-secret", repr(result))
        self.assertEqual(context.audit_sink.events[-1].event_type, "run_failed")
        self.assertEqual(
            context.audit_sink.events[-1].details,
            {"outcome": "human_takeover"},
        )


class SDKAgentRunnerTest(unittest.IsolatedAsyncioTestCase):
    async def test_limits_sdk_runs_to_six_turns(self):
        runner = SDKAgentRunner()
        start = SimpleNamespace(name="Copilot Router Agent")
        context = make_context()
        run_config = MagicMock()
        expected = SimpleNamespace()

        with patch(
            "claimguard.agent_runtime.runtime.Runner.run",
            new=AsyncMock(return_value=expected),
        ) as run:
            result = await runner.run(
                start,
                "等待期是什么？",
                context=context,
                run_config=run_config,
            )

        self.assertIs(result, expected)
        run.assert_awaited_once_with(
            start,
            "等待期是什么？",
            context=context,
            run_config=run_config,
            max_turns=6,
        )


if __name__ == "__main__":
    unittest.main()
