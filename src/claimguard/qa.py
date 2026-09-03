from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

from claimguard.conversation import Conversation
from claimguard.embeddings import EmbeddingClient
from claimguard.knowledge import KnowledgeIndex, retrieve_clauses
from claimguard.rule_runner import run_rules
from claimguard.rules import RuleCatalog


@dataclass(frozen=True)
class GroundingEvidence:
    clause_id: str
    clause_title: str
    clause_text: str
    source_path: str
    retrieval_score: float


@dataclass(frozen=True)
class Finding:
    rule_id: str
    rule_name: str
    category: str
    risk_level: str
    evidence: str
    recommendation: str
    grounding: Optional[GroundingEvidence] = None


@dataclass(frozen=True)
class QAReport:
    conversation_id: str
    scenario: str
    score: int
    findings: list[Finding]

    def to_dict(self) -> dict:
        return asdict(self)


def generate_qa_report(
    conversation: Conversation,
    catalog: RuleCatalog,
    *,
    knowledge_index: Optional[KnowledgeIndex] = None,
    embedding_client: Optional[EmbeddingClient] = None,
) -> QAReport:
    findings = []
    for match in run_rules(conversation):
        rule = catalog.get(match.rule_id)
        findings.append(
            Finding(
                rule_id=rule.id,
                rule_name=rule.name,
                category=rule.category,
                risk_level=rule.risk_level,
                evidence=match.evidence,
                recommendation=(
                    "Replace the response with a clear, empathetic, "
                    f"policy-grounded explanation for {rule.id}."
                ),
                grounding=_retrieve_grounding_evidence(
                    match.evidence, rule.name, rule.category, knowledge_index, embedding_client
                ),
            )
        )

    return QAReport(
        conversation_id=conversation.id,
        scenario=conversation.scenario,
        score=max(0, 100 - (10 * len(findings))),
        findings=findings,
    )


def _retrieve_grounding_evidence(
    customer_evidence: str,
    rule_name: str,
    category: str,
    knowledge_index: Optional[KnowledgeIndex],
    embedding_client: Optional[EmbeddingClient],
) -> Optional[GroundingEvidence]:
    if (
        category != "knowledge_grounded"
        or knowledge_index is None
        or embedding_client is None
    ):
        return None

    retrieved = retrieve_clauses(
        f"{customer_evidence} {rule_name}", knowledge_index, embedding_client, top_k=1
    )
    if not retrieved:
        return None

    result = retrieved[0]
    return GroundingEvidence(
        clause_id=result.clause.id,
        clause_title=result.clause.title,
        clause_text=result.clause.content,
        source_path=result.clause.source_path,
        retrieval_score=result.score,
    )
