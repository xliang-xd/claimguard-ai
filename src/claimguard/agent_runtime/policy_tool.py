from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from agents import FunctionTool, RunContextWrapper, function_tool

from claimguard.agent_runtime.audit import AuditEvent
from claimguard.agent_runtime.state import CopilotContext
from claimguard.knowledge import retrieve_clauses


@dataclass(frozen=True)
class PolicyClauseEvidence:
    id: str
    title: str
    content: str
    source_path: str
    score: float


@dataclass(frozen=True)
class PolicySearchResult:
    status: Literal["success", "no_evidence"]
    clauses: list[PolicyClauseEvidence]
    audit_id: str


def search_policy_clauses(
    context: CopilotContext,
    query: str,
    top_k: int = 3,
    minimum_score: float = 0.25,
) -> PolicySearchResult:
    retrieved = retrieve_clauses(
        query,
        context.knowledge_index,
        context.embedding_client,
        top_k=top_k,
    )
    evidence = [
        PolicyClauseEvidence(
            id=item.clause.id,
            title=item.clause.title,
            content=item.clause.content,
            source_path=item.clause.source_path,
            score=item.score,
        )
        for item in retrieved
        if item.score >= minimum_score
    ]
    audit_id = context.audit_sink.record(
        AuditEvent(
            event_type="policy_search",
            tenant_id=context.tenant_id,
            session_id=context.session_id,
            user_id=context.user_id,
            details={
                "query_length": len(query.strip()),
                "clause_ids": [item.id for item in evidence],
                "result_count": len(evidence),
            },
        )
    )
    return PolicySearchResult(
        status="success" if evidence else "no_evidence",
        clauses=evidence,
        audit_id=audit_id,
    )


@function_tool
def search_policy_clauses_tool(
    wrapper: RunContextWrapper[CopilotContext],
    query: str,
) -> dict[str, object]:
    """检索支持当前保险问题的保单条款，只返回可引用的条款证据。"""
    return asdict(search_policy_clauses(wrapper.context, query))


def build_search_policy_tool() -> FunctionTool:
    return search_policy_clauses_tool
