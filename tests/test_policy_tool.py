import asyncio
import json
from pathlib import Path
import sys
import unittest

from agents.tool_context import ToolContext
from agents.usage import InputTokensDetails, OutputTokensDetails, Usage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.agent_runtime.audit import InMemoryAuditSink
from claimguard.agent_runtime.evidence import EvidenceLedger
from claimguard.agent_runtime.policy_tool import (
    build_search_policy_tool,
    search_policy_clauses,
    search_policy_clauses_tool,
)
from claimguard.agent_runtime.state import CopilotContext
from claimguard.knowledge import IndexedClause, KnowledgeIndex, PolicyClause
from claimguard.reranking import RerankingError


class StaticEmbeddingClient:
    model = "test-model"

    def __init__(self, vector):
        self.vector = vector

    def embed(self, texts):
        return [self.vector for _ in texts]


class StaticReranker:
    model = "test-reranker"

    def __init__(self, scores):
        self.scores = scores

    def rerank(self, query, documents):
        return self.scores


class FailingReranker:
    model = "test-reranker"

    def rerank(self, query, documents):
        raise RerankingError("客户私密问题：条款私密正文")


def build_test_context(scores_below_threshold=False, rerank_scores=None):
    clause = PolicyClause("18", "等待期", "等待期内疾病治疗不予赔付。", "policy.md")
    index = KnowledgeIndex(
        clauses=[IndexedClause(clause, [1.0, 0.0])],
        embedding_model="test-model",
        dimensions=2,
    )
    query_vector = [0.0, 1.0] if scores_below_threshold else [1.0, 0.0]
    return CopilotContext(
        tenant_id="tenant-a",
        session_id="session-1",
        user_id="agent-7",
        knowledge_index=index,
        embedding_client=StaticEmbeddingClient(query_vector),
        audit_sink=InMemoryAuditSink(),
        reranker=StaticReranker(rerank_scores or [0.9]),
        evidence_ledger=EvidenceLedger(),
    )


def build_tool_context(context, arguments):
    usage = Usage(
        input_tokens_details=InputTokensDetails(
            cached_tokens=0,
            cache_write_tokens=0,
        ),
        output_tokens_details=OutputTokensDetails(reasoning_tokens=0),
    )
    return ToolContext(
        context,
        usage=usage,
        tool_name="search_policy_clauses_tool",
        tool_call_id="call-1",
        tool_arguments=arguments,
    )


class PolicyToolTest(unittest.TestCase):
    def test_returns_reranked_clause_evidence_and_records_metadata_only_audit(self):
        context = build_test_context()
        query = " 等待期内就诊为什么拒赔？ "

        result = search_policy_clauses(context, query)

        self.assertEqual(result.status, "success")
        self.assertEqual(result.clauses[0].id, "18")
        self.assertEqual(result.clauses[0].title, "等待期")
        self.assertEqual(result.clauses[0].content, "等待期内疾病治疗不予赔付。")
        self.assertEqual(result.clauses[0].source_path, "policy.md")
        self.assertEqual(result.clauses[0].score, 0.9)
        self.assertEqual(result.audit_id, "audit-000001")
        self.assertEqual(context.audit_sink.events[-1].event_type, "policy_search")
        self.assertEqual(
            context.audit_sink.events[-1].details,
            {
                "query_length": 12,
                "clause_ids": ["18"],
                "result_count": 1,
                "minimum_rerank_score": 0.9,
                "maximum_rerank_score": 0.9,
            },
        )

    def test_returns_no_evidence_without_inventing_a_clause(self):
        context = build_test_context(scores_below_threshold=True, rerank_scores=[0.1])

        result = search_policy_clauses(context, "无关问题")

        self.assertEqual(result.status, "no_evidence")
        self.assertEqual(result.clauses, [])
        self.assertEqual(
            context.audit_sink.events[-1].details,
            {
                "query_length": 4,
                "clause_ids": [],
                "result_count": 0,
                "minimum_rerank_score": None,
                "maximum_rerank_score": None,
            },
        )

    def test_policy_search_records_only_selected_reranked_evidence(self):
        clauses = [
            IndexedClause(
                PolicyClause("18", "等待期", "等待期内疾病治疗不予赔付。", "policy.md"),
                [1.0, 0.0],
            ),
            IndexedClause(
                PolicyClause("19", "观察期", "观察期内治疗不予赔付。", "policy.md"),
                [0.9, 0.1],
            ),
        ]
        context = build_test_context(rerank_scores=[0.9, 0.1])
        context = CopilotContext(
            tenant_id=context.tenant_id,
            session_id=context.session_id,
            user_id=context.user_id,
            knowledge_index=KnowledgeIndex(
                clauses=clauses,
                embedding_model="test-model",
                dimensions=2,
            ),
            embedding_client=context.embedding_client,
            audit_sink=context.audit_sink,
            reranker=context.reranker,
            evidence_ledger=context.evidence_ledger,
        )

        result = search_policy_clauses(context, "等待期", top_k=2)

        self.assertEqual([item.id for item in result.clauses], ["18"])
        self.assertEqual(
            [record.clause_id for record in context.evidence_ledger.snapshot()],
            ["18"],
        )
        self.assertEqual(context.evidence_ledger.snapshot()[0].retrieval_score, 1.0)
        self.assertEqual(context.evidence_ledger.snapshot()[0].rerank_score, 0.9)

    def test_policy_search_audit_contains_no_clause_content(self):
        context = build_test_context()

        search_policy_clauses(context, "等待期")

        details = context.audit_sink.events[-1].details
        self.assertNotIn("content", details)
        self.assertNotIn("等待期内疾病治疗不予赔付。", repr(details))

    def test_policy_search_hides_reranker_error_details(self):
        context = build_test_context()
        context = CopilotContext(
            tenant_id=context.tenant_id,
            session_id=context.session_id,
            user_id=context.user_id,
            knowledge_index=context.knowledge_index,
            embedding_client=context.embedding_client,
            audit_sink=context.audit_sink,
            reranker=FailingReranker(),
            evidence_ledger=context.evidence_ledger,
        )

        with self.assertRaisesRegex(RerankingError, "重排请求失败") as error:
            search_policy_clauses(context, "客户私密问题")

        self.assertNotIn("客户私密问题", str(error.exception))
        self.assertNotIn("条款私密正文", str(error.exception))

    def test_builds_read_only_agents_tool_that_serializes_search_result(self):
        context = build_test_context()
        tool = build_search_policy_tool()
        arguments = json.dumps({"query": "等待期内就诊为什么拒赔？"})

        result = asyncio.run(
            tool.on_invoke_tool(
                build_tool_context(context, arguments),
                arguments,
            )
        )

        self.assertIs(tool, search_policy_clauses_tool)
        self.assertFalse(tool.needs_approval)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["clauses"][0]["id"], "18")
        self.assertEqual(result["audit_id"], "audit-000001")


if __name__ == "__main__":
    unittest.main()
