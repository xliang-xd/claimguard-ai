import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.agent_runtime.agents import CopilotAgentOutput
from claimguard.agent_runtime.audit import InMemoryAuditSink
from claimguard.agent_runtime.evidence import EvidenceLedger, EvidenceRecord
from claimguard.agent_runtime.runtime import CopilotRuntime, SDKAgentRunner
from claimguard.agent_runtime.state import (
    ConversationState,
    CopilotContext,
    InMemorySessionStore,
)
from claimguard.citation_judge import CitationVerdict


def evidence_record(clause_id="18"):
    return EvidenceRecord(
        clause_id=clause_id,
        title="等待期",
        content="等待期为三十日。",
        source_path="policy.md",
        retrieval_score=0.9,
        rerank_score=0.8,
    )


def supported(*citation_ids):
    return CitationVerdict(
        status="supported",
        citations=tuple(citation_ids),
        reason_code="citation_supported",
    )


def unsupported():
    return CitationVerdict(
        status="unsupported",
        citations=(),
        reason_code="citation_unsupported",
    )


class StaticJudge:
    def __init__(self, verdict):
        self.verdict = verdict
        self.calls = []

    def judge(self, draft, evidence):
        self.calls.append((draft, evidence))
        return self.verdict


class FailingJudge:
    def judge(self, draft, evidence):
        raise RuntimeError("Authorization: Bearer judge-secret")


class ScriptedRunner:
    def __init__(self, last_agent_name, output, result_input_items=(), record_evidence=True):
        self.last_agent_name = last_agent_name
        self.output = output
        self.result_input_items = result_input_items
        self.starting_agent_names = []
        self.inputs = []
        self.record_evidence = record_evidence

    async def run(self, starting_agent, agent_input, *, context, run_config):
        self.starting_agent_names.append(starting_agent.name)
        self.inputs.append(agent_input)
        if self.record_evidence:
            context.evidence_ledger.record([evidence_record()])
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


class SerializedRunner:
    def __init__(self):
        self.first_turn_started = asyncio.Event()
        self.release_first_turn = asyncio.Event()
        self.inputs = []

    async def run(self, starting_agent, agent_input, *, context, run_config):
        self.inputs.append(agent_input)
        context.evidence_ledger.record([evidence_record()])
        if len(self.inputs) == 1:
            self.first_turn_started.set()
            await self.release_first_turn.wait()
        if isinstance(agent_input, str):
            input_items = [{"role": "user", "content": agent_input}]
        else:
            input_items = [*agent_input]
        return ScriptedRunResult(
            "Policy Agent",
            CopilotAgentOutput(status="draft_ready", draft="客服草稿：已处理"),
            input_items,
        )


class ReusableSerializedRunner:
    def __init__(self):
        self.inputs = []

    def prepare_pair(self):
        self._pair_start = len(self.inputs)
        self.first_turn_started = asyncio.Event()
        self.release_first_turn = asyncio.Event()
        return self._pair_start

    async def run(self, starting_agent, agent_input, *, context, run_config):
        self.inputs.append(agent_input)
        context.evidence_ledger.record([evidence_record()])
        if len(self.inputs) == self._pair_start + 1:
            self.first_turn_started.set()
            await self.release_first_turn.wait()
        if isinstance(agent_input, str):
            input_items = [{"role": "user", "content": agent_input}]
        else:
            input_items = [*agent_input]
        return ScriptedRunResult(
            "Policy Agent",
            CopilotAgentOutput(status="draft_ready", draft="客服草稿：已处理"),
            input_items,
        )


class HotAndColdSessionRunner:
    def __init__(self):
        self.hot_turn_started = asyncio.Event()
        self.release_hot_turn = asyncio.Event()
        self.cold_turn_started = asyncio.Event()

    async def run(self, starting_agent, agent_input, *, context, run_config):
        if context.session_id == "hot-session" and not self.hot_turn_started.is_set():
            self.hot_turn_started.set()
            await self.release_hot_turn.wait()
        if context.session_id == "cold-session":
            self.cold_turn_started.set()
        context.evidence_ledger.record([evidence_record()])
        input_items = (
            [{"role": "user", "content": agent_input}]
            if isinstance(agent_input, str)
            else [*agent_input]
        )
        return ScriptedRunResult(
            "Policy Agent",
            CopilotAgentOutput(status="draft_ready", draft="客服草稿：已处理"),
            input_items,
        )


class CrossLoopSerializedRunner:
    def __init__(self):
        self.first_turn_started = threading.Event()
        self.release_first_turn = threading.Event()
        self.inputs = []
        self._inputs_guard = threading.Lock()

    async def run(self, starting_agent, agent_input, *, context, run_config):
        with self._inputs_guard:
            self.inputs.append(agent_input)
            is_first_turn = len(self.inputs) == 1
        if is_first_turn:
            self.first_turn_started.set()
            await asyncio.to_thread(self.release_first_turn.wait)
        context.evidence_ledger.record([evidence_record()])
        input_items = (
            [{"role": "user", "content": agent_input}]
            if isinstance(agent_input, str)
            else [*agent_input]
        )
        return ScriptedRunResult(
            "Policy Agent",
            CopilotAgentOutput(status="draft_ready", draft="客服草稿：已处理"),
            input_items,
        )


class LegacySessionStore:
    def __init__(self):
        self.states = {}

    def load(self, tenant_id, session_id):
        return self.states.get((tenant_id, session_id))

    def save(self, state):
        self.states[(state.tenant_id, state.session_id)] = state


class FailingCompletionAuditSink:
    def __init__(self):
        self.events = []

    def record(self, event):
        if event.event_type == "run_completed":
            raise RuntimeError("Authorization: Bearer test-secret")
        self.events.append(event)
        return f"audit-{len(self.events):06d}"


def make_context():
    return CopilotContext(
        tenant_id="tenant-a",
        session_id="session-1",
        user_id="agent-7",
        knowledge_index=MagicMock(),
        embedding_client=MagicMock(),
        audit_sink=InMemoryAuditSink(),
        reranker=MagicMock(),
        evidence_ledger=EvidenceLedger(),
    )


def make_runtime(runner, store, judge=...):
    router = SimpleNamespace(name="Copilot Router Agent")
    policy = SimpleNamespace(name="Policy Agent")
    agents = SimpleNamespace(
        router=router,
        by_name={router.name: router, policy.name: policy},
    )
    if judge is ...:
        judge = StaticJudge(supported("18"))
    return CopilotRuntime(
        agents=agents,
        run_config=MagicMock(),
        session_store=store,
        runner=runner,
        citation_judge=judge,
    )


async def run_serialized_pair(
    first_runtime,
    second_runtime,
    runner,
    first_message,
    second_message,
):
    pair_start = runner.prepare_pair()
    context = make_context()
    first_turn = asyncio.create_task(first_runtime.run_turn(context, first_message))
    await runner.first_turn_started.wait()
    second_turn = asyncio.create_task(second_runtime.run_turn(context, second_message))
    await asyncio.sleep(0)
    inputs_before_release = list(runner.inputs[pair_start:])
    runner.release_first_turn.set()
    return inputs_before_release, await asyncio.gather(first_turn, second_turn)


class CopilotRuntimeTest(unittest.IsolatedAsyncioTestCase):
    async def test_runtime_package_exports_citation_judge_contract(self):
        from claimguard.agent_runtime import CitationJudge as PublicCitationJudge
        from claimguard.agent_runtime import CitationVerdict as PublicCitationVerdict

        from claimguard.citation_judge import CitationJudge, CitationVerdict

        self.assertIs(PublicCitationJudge, CitationJudge)
        self.assertIs(PublicCitationVerdict, CitationVerdict)

    async def test_supported_verdict_saves_state_and_delivers_draft(self):
        store = InMemorySessionStore()
        context = make_context()
        judge = StaticJudge(supported("18"))

        result = await make_runtime(
            ScriptedRunner(
                last_agent_name="Policy Agent",
                output=CopilotAgentOutput(status="draft_ready", draft="客服草稿：等待期说明"),
            ),
            store,
            judge=judge,
        ).run_turn(context, "等待期")

        self.assertEqual(result.status, "draft_ready")
        self.assertEqual(result.draft, "客服草稿：等待期说明")
        self.assertIsNotNone(store.load("tenant-a", "session-1"))
        self.assertEqual(judge.calls[0][1], (evidence_record(),))
        self.assertEqual(context.audit_sink.events[-1].event_type, "run_completed")
        self.assertEqual(
            context.audit_sink.events[-1].details,
            {"citation_status": "supported", "citation_ids": ("18",)},
        )

    async def test_unsupported_verdict_does_not_save_or_deliver(self):
        store = InMemorySessionStore()
        context = make_context()

        result = await make_runtime(
            ScriptedRunner(
                last_agent_name="Policy Agent",
                output=CopilotAgentOutput(status="draft_ready", draft="客服草稿：等待期说明"),
            ),
            store,
            judge=StaticJudge(unsupported()),
        ).run_turn(context, "等待期")

        self.assertEqual((result.status, result.draft), ("human_takeover", ""))
        self.assertIsNone(store.load("tenant-a", "session-1"))
        self.assertEqual(context.audit_sink.events[-1].event_type, "citation_failed")
        self.assertEqual(
            context.audit_sink.events[-1].details,
            {
                "citation_status": "unsupported",
                "citation_ids": (),
                "failure_category": "unsupported_verdict",
            },
        )

    async def test_empty_ledger_does_not_call_judge_or_save_state(self):
        store = InMemorySessionStore()
        context = make_context()
        judge = StaticJudge(supported("18"))

        result = await make_runtime(
            ScriptedRunner(
                last_agent_name="Policy Agent",
                output=CopilotAgentOutput(status="draft_ready", draft="客服草稿：等待期说明"),
                record_evidence=False,
            ),
            store,
            judge=judge,
        ).run_turn(context, "等待期")

        self.assertEqual((result.status, result.draft), ("human_takeover", ""))
        self.assertEqual(judge.calls, [])
        self.assertIsNone(store.load("tenant-a", "session-1"))
        self.assertEqual(
            context.audit_sink.events[-1].details,
            {
                "citation_status": "not_judged",
                "citation_ids": (),
                "failure_category": "no_evidence",
            },
        )

    async def test_missing_judge_fails_closed_after_evidence_is_found(self):
        store = InMemorySessionStore()
        context = make_context()

        result = await make_runtime(
            ScriptedRunner(
                last_agent_name="Policy Agent",
                output=CopilotAgentOutput(status="draft_ready", draft="客服草稿：等待期说明"),
            ),
            store,
            judge=None,
        ).run_turn(context, "等待期")

        self.assertEqual((result.status, result.draft), ("human_takeover", ""))
        self.assertIsNone(store.load("tenant-a", "session-1"))
        self.assertEqual(
            context.audit_sink.events[-1].details,
            {
                "citation_status": "not_judged",
                "citation_ids": (),
                "failure_category": "judge_unavailable",
            },
        )

    async def test_judge_error_fails_closed_without_disclosing_exception(self):
        store = InMemorySessionStore()
        context = make_context()

        result = await make_runtime(
            ScriptedRunner(
                last_agent_name="Policy Agent",
                output=CopilotAgentOutput(status="draft_ready", draft="客服草稿：等待期说明"),
            ),
            store,
            judge=FailingJudge(),
        ).run_turn(context, "等待期")

        self.assertEqual((result.status, result.draft), ("human_takeover", ""))
        self.assertNotIn("judge-secret", repr(result))
        self.assertIsNone(store.load("tenant-a", "session-1"))
        self.assertEqual(
            context.audit_sink.events[-1].details,
            {
                "citation_status": "not_judged",
                "citation_ids": (),
                "failure_category": "judge_error",
            },
        )

    async def test_unknown_judge_citation_is_not_audited_or_delivered(self):
        store = InMemorySessionStore()
        context = make_context()

        result = await make_runtime(
            ScriptedRunner(
                last_agent_name="Policy Agent",
                output=CopilotAgentOutput(status="draft_ready", draft="客服草稿：等待期说明"),
            ),
            store,
            judge=StaticJudge(supported("unknown-clause")),
        ).run_turn(context, "等待期")

        self.assertEqual((result.status, result.draft), ("human_takeover", ""))
        self.assertIsNone(store.load("tenant-a", "session-1"))
        self.assertEqual(
            context.audit_sink.events[-1].details,
            {
                "citation_status": "supported",
                "citation_ids": (),
                "failure_category": "unknown_citation",
            },
        )

    async def test_failed_completion_audit_does_not_save_state_after_supported_verdict(self):
        store = InMemorySessionStore()
        context = make_context()
        context = CopilotContext(
            tenant_id=context.tenant_id,
            session_id=context.session_id,
            user_id=context.user_id,
            knowledge_index=context.knowledge_index,
            embedding_client=context.embedding_client,
            audit_sink=FailingCompletionAuditSink(),
            reranker=context.reranker,
            evidence_ledger=context.evidence_ledger,
        )

        result = await make_runtime(
            ScriptedRunner(
                last_agent_name="Policy Agent",
                output=CopilotAgentOutput(status="draft_ready", draft="客服草稿：等待期说明"),
            ),
            store,
            judge=StaticJudge(supported("18")),
        ).run_turn(context, "等待期")

        self.assertEqual((result.status, result.draft), ("human_takeover", ""))
        self.assertIsNone(store.load("tenant-a", "session-1"))
        self.assertEqual(context.audit_sink.events[-1].event_type, "citation_failed")
        self.assertEqual(
            context.audit_sink.events[-1].details,
            {
                "citation_status": "supported",
                "citation_ids": ("18",),
                "failure_category": "audit_failed",
            },
        )

    async def test_next_turn_clears_prior_ledger_evidence(self):
        store = InMemorySessionStore()
        context = make_context()
        runner = ScriptedRunner(
            last_agent_name="Policy Agent",
            output=CopilotAgentOutput(status="draft_ready", draft="客服草稿：等待期说明"),
        )
        judge = StaticJudge(supported("18"))
        runtime = make_runtime(runner, store, judge=judge)

        first_result = await runtime.run_turn(context, "等待期")
        state_after_first_turn = store.load("tenant-a", "session-1")
        runner.record_evidence = False
        context.evidence_ledger.record([evidence_record("stale-clause")])
        second_result = await runtime.run_turn(context, "续问")

        self.assertEqual(first_result.status, "draft_ready")
        self.assertEqual((second_result.status, second_result.draft), ("human_takeover", ""))
        self.assertEqual(context.evidence_ledger.snapshot(), ())
        self.assertEqual(len(judge.calls), 1)
        self.assertEqual(store.load("tenant-a", "session-1"), state_after_first_turn)

    async def test_hot_session_waiters_do_not_block_a_cold_session(self):
        asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=1))
        runner = HotAndColdSessionRunner()
        runtime = make_runtime(runner, InMemorySessionStore())
        hot_context = CopilotContext(
            tenant_id="tenant-a",
            session_id="hot-session",
            user_id="agent-7",
            knowledge_index=MagicMock(),
            embedding_client=MagicMock(),
            audit_sink=InMemoryAuditSink(),
            reranker=MagicMock(),
            evidence_ledger=EvidenceLedger(),
        )
        cold_context = CopilotContext(
            tenant_id="tenant-a",
            session_id="cold-session",
            user_id="agent-7",
            knowledge_index=MagicMock(),
            embedding_client=MagicMock(),
            audit_sink=InMemoryAuditSink(),
            reranker=MagicMock(),
            evidence_ledger=EvidenceLedger(),
        )
        hot_turn = asyncio.create_task(runtime.run_turn(hot_context, "第一条热会话消息"))
        await runner.hot_turn_started.wait()
        waiting_turns = [
            asyncio.create_task(runtime.run_turn(hot_context, f"排队消息 {index}"))
            for index in range(32)
        ]
        await asyncio.sleep(0)
        cold_turn = asyncio.create_task(runtime.run_turn(cold_context, "冷会话消息"))

        try:
            await asyncio.wait_for(runner.cold_turn_started.wait(), timeout=0.2)
        finally:
            runner.release_hot_turn.set()
            await asyncio.gather(hot_turn, *waiting_turns, cold_turn)

        self.assertEqual((await cold_turn).status, "draft_ready")

    async def test_legacy_store_without_exclusive_session_still_runs_turn(self):
        store = LegacySessionStore()
        result = await make_runtime(
            ScriptedRunner(
                last_agent_name="Policy Agent",
                output=CopilotAgentOutput(status="draft_ready", draft="客服草稿：已处理"),
                result_input_items=({"role": "user", "content": "旧接口消息"},),
            ),
            store,
        ).run_turn(make_context(), "旧接口消息")

        self.assertEqual(result.status, "draft_ready")
        self.assertEqual(store.load("tenant-a", "session-1").current_agent, "Policy Agent")

    async def test_legacy_store_serializes_turns_within_one_runtime(self):
        runner = SerializedRunner()
        runtime = make_runtime(runner, LegacySessionStore())
        context = make_context()

        first_turn = asyncio.create_task(runtime.run_turn(context, "第一条消息"))
        await runner.first_turn_started.wait()
        second_turn = asyncio.create_task(runtime.run_turn(context, "第二条消息"))
        await asyncio.sleep(0)

        self.assertEqual(runner.inputs, ["第一条消息"])

        runner.release_first_turn.set()
        await asyncio.gather(first_turn, second_turn)

        self.assertEqual(
            runner.inputs[1],
            [
                {"role": "user", "content": "第一条消息"},
                {"role": "user", "content": "第二条消息"},
            ],
        )

    async def test_shared_store_serializes_turns_from_distinct_runtimes(self):
        runner = ReusableSerializedRunner()
        store = InMemorySessionStore()
        first_runtime = make_runtime(runner, store)
        second_runtime = make_runtime(runner, store)

        inputs_before_release, results = await run_serialized_pair(
            first_runtime,
            second_runtime,
            runner,
            "第一条消息",
            "第二条消息",
        )

        self.assertEqual(inputs_before_release, ["第一条消息"])
        self.assertEqual([result.status for result in results], ["draft_ready"] * 2)
        self.assertEqual(
            runner.inputs[1],
            [
                {"role": "user", "content": "第一条消息"},
                {"role": "user", "content": "第二条消息"},
            ],
        )

    async def test_same_session_turns_are_serialized_and_preserve_history(self):
        runner = SerializedRunner()
        store = InMemorySessionStore()
        runtime = make_runtime(runner, store)
        context = make_context()

        first_turn = asyncio.create_task(runtime.run_turn(context, "第一条消息"))
        await runner.first_turn_started.wait()
        second_turn = asyncio.create_task(runtime.run_turn(context, "第二条消息"))
        await asyncio.sleep(0)

        self.assertEqual(runner.inputs, ["第一条消息"])

        runner.release_first_turn.set()
        await asyncio.gather(first_turn, second_turn)

        self.assertEqual(
            runner.inputs[1],
            [
                {"role": "user", "content": "第一条消息"},
                {"role": "user", "content": "第二条消息"},
            ],
        )
        self.assertEqual(
            store.load("tenant-a", "session-1").input_items,
            (
                {"role": "user", "content": "第一条消息"},
                {"role": "user", "content": "第二条消息"},
            ),
        )

    async def test_failed_completion_audit_does_not_advance_session_state(self):
        prior_state = ConversationState(
            "tenant-a",
            "session-1",
            "agent-7",
            "Policy Agent",
            ({"role": "user", "content": "已有消息"},),
        )
        store = InMemorySessionStore()
        store.save(prior_state)
        runner = ScriptedRunner(
            last_agent_name="Policy Agent",
            output=CopilotAgentOutput(status="draft_ready", draft="客服草稿：不应保存"),
            result_input_items=(
                {"role": "user", "content": "已有消息"},
                {"role": "user", "content": "新消息"},
            ),
        )
        context = make_context()
        context = CopilotContext(
            tenant_id=context.tenant_id,
            session_id=context.session_id,
            user_id=context.user_id,
            knowledge_index=context.knowledge_index,
            embedding_client=context.embedding_client,
            audit_sink=FailingCompletionAuditSink(),
            reranker=context.reranker,
            evidence_ledger=context.evidence_ledger,
        )

        result = await make_runtime(runner, store).run_turn(context, "新消息")

        self.assertEqual(result.status, "human_takeover")
        self.assertEqual(result.draft, "")
        self.assertNotIn("test-secret", repr(result))
        self.assertEqual(store.load("tenant-a", "session-1"), prior_state)
        self.assertEqual(context.audit_sink.events[-1].event_type, "citation_failed")
        self.assertEqual(
            context.audit_sink.events[-1].details,
            {
                "citation_status": "supported",
                "citation_ids": ("18",),
                "failure_category": "audit_failed",
            },
        )

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
            {"citation_status": "supported", "citation_ids": ("18",)},
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
        self.assertEqual(context.audit_sink.events[-1].event_type, "citation_failed")
        self.assertEqual(
            context.audit_sink.events[-1].details,
            {
                "citation_status": "not_judged",
                "citation_ids": (),
                "failure_category": "runtime_error",
            },
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
        self.assertEqual(context.audit_sink.events[-1].event_type, "citation_failed")
        self.assertEqual(
            context.audit_sink.events[-1].details,
            {
                "citation_status": "not_judged",
                "citation_ids": (),
                "failure_category": "runtime_error",
            },
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
        self.assertEqual(context.audit_sink.events[-1].event_type, "citation_failed")
        self.assertEqual(
            context.audit_sink.events[-1].details,
            {
                "citation_status": "not_judged",
                "citation_ids": (),
                "failure_category": "runtime_error",
            },
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
        self.assertEqual(context.audit_sink.events[-1].event_type, "citation_failed")
        self.assertEqual(
            context.audit_sink.events[-1].details,
            {
                "citation_status": "not_judged",
                "citation_ids": (),
                "failure_category": "invalid_output",
            },
        )


class CopilotRuntimeCrossEventLoopTest(unittest.TestCase):
    def test_shared_store_serializes_distinct_runtimes_on_concurrent_event_loops(self):
        runner = CrossLoopSerializedRunner()
        store = InMemorySessionStore()
        first_runtime = make_runtime(runner, store)
        second_runtime = make_runtime(runner, store)
        context = make_context()
        first_results = []

        def run_first_turn():
            first_results.append(asyncio.run(first_runtime.run_turn(context, "第一条消息")))

        async def run_second_turn():
            first_thread = threading.Thread(target=run_first_turn)
            first_thread.start()
            try:
                await asyncio.to_thread(runner.first_turn_started.wait)
                second_turn = asyncio.create_task(
                    second_runtime.run_turn(context, "第二条消息")
                )
                await asyncio.sleep(0)
                self.assertEqual(runner.inputs, ["第一条消息"])
                runner.release_first_turn.set()
                return await second_turn
            finally:
                runner.release_first_turn.set()
                await asyncio.to_thread(first_thread.join)
                self.assertFalse(first_thread.is_alive())

        second_result = asyncio.run(run_second_turn())

        self.assertEqual([result.status for result in first_results], ["draft_ready"])
        self.assertEqual(second_result.status, "draft_ready")
        self.assertEqual(
            store.load("tenant-a", "session-1").input_items,
            (
                {"role": "user", "content": "第一条消息"},
                {"role": "user", "content": "第二条消息"},
            ),
        )

    def test_store_session_serialization_can_be_reused_across_event_loops(self):
        runner = ReusableSerializedRunner()
        store = InMemorySessionStore()
        runtime = make_runtime(runner, store)

        first_inputs, first_results = asyncio.run(
            run_serialized_pair(
                runtime,
                runtime,
                runner,
                "第一条消息",
                "第二条消息",
            )
        )
        second_inputs, second_results = asyncio.run(
            run_serialized_pair(
                runtime,
                runtime,
                runner,
                "第三条消息",
                "第四条消息",
            )
        )

        self.assertEqual(first_inputs, ["第一条消息"])
        self.assertEqual(
            second_inputs,
            [
                [
                    {"role": "user", "content": "第一条消息"},
                    {"role": "user", "content": "第二条消息"},
                    {"role": "user", "content": "第三条消息"},
                ]
            ],
        )
        self.assertEqual(
            [result.status for result in [*first_results, *second_results]],
            ["draft_ready"] * 4,
        )
        self.assertEqual(
            store.load("tenant-a", "session-1").input_items,
            (
                {"role": "user", "content": "第一条消息"},
                {"role": "user", "content": "第二条消息"},
                {"role": "user", "content": "第三条消息"},
                {"role": "user", "content": "第四条消息"},
            ),
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
