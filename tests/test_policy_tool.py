import asyncio
import json
from pathlib import Path
import sys
import unittest

from agents.tool_context import ToolContext
from agents.usage import InputTokensDetails, OutputTokensDetails, Usage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.agent_runtime.audit import InMemoryAuditSink
from claimguard.agent_runtime.policy_tool import (
    build_search_policy_tool,
    search_policy_clauses,
    search_policy_clauses_tool,
)
from claimguard.agent_runtime.state import CopilotContext
from claimguard.knowledge import IndexedClause, KnowledgeIndex, PolicyClause


class StaticEmbeddingClient:
    model = "test-model"

    def __init__(self, vector):
        self.vector = vector

    def embed(self, texts):
        return [self.vector for _ in texts]


def build_test_context(scores_below_threshold=False):
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
    def test_returns_ranked_clause_evidence_and_records_metadata_only_audit(self):
        context = build_test_context()
        query = " 等待期内就诊为什么拒赔？ "

        result = search_policy_clauses(context, query)

        self.assertEqual(result.status, "success")
        self.assertEqual(result.clauses[0].id, "18")
        self.assertEqual(result.clauses[0].title, "等待期")
        self.assertEqual(result.clauses[0].content, "等待期内疾病治疗不予赔付。")
        self.assertEqual(result.clauses[0].source_path, "policy.md")
        self.assertEqual(result.clauses[0].score, 1.0)
        self.assertEqual(result.audit_id, "audit-000001")
        self.assertEqual(context.audit_sink.events[-1].event_type, "policy_search")
        self.assertEqual(
            context.audit_sink.events[-1].details,
            {
                "query_length": 12,
                "clause_ids": ["18"],
                "result_count": 1,
            },
        )

    def test_returns_no_evidence_without_inventing_a_clause(self):
        context = build_test_context(scores_below_threshold=True)

        result = search_policy_clauses(context, "无关问题")

        self.assertEqual(result.status, "no_evidence")
        self.assertEqual(result.clauses, [])
        self.assertEqual(
            context.audit_sink.events[-1].details,
            {
                "query_length": 4,
                "clause_ids": [],
                "result_count": 0,
            },
        )

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
