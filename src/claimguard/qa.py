from __future__ import annotations

from dataclasses import asdict, dataclass

from claimguard.conversation import Conversation
from claimguard.rules import RuleCatalog


@dataclass(frozen=True)
class Finding:
    rule_id: str
    rule_name: str
    category: str
    risk_level: str
    evidence: str
    recommendation: str


@dataclass(frozen=True)
class QAReport:
    conversation_id: str
    scenario: str
    score: int
    findings: list[Finding]

    def to_dict(self) -> dict:
        return asdict(self)


def generate_qa_report(conversation: Conversation, catalog: RuleCatalog) -> QAReport:
    findings = []
    evidence = _agent_evidence(conversation)
    for rule_id in conversation.expected_risks:
        rule = catalog.get(rule_id)
        findings.append(
            Finding(
                rule_id=rule.id,
                rule_name=rule.name,
                category=rule.category,
                risk_level=rule.risk_level,
                evidence=evidence,
                recommendation=(
                    "Replace the response with a clear, empathetic, "
                    f"policy-grounded explanation for {rule.id}."
                ),
            )
        )

    return QAReport(
        conversation_id=conversation.id,
        scenario=conversation.scenario,
        score=max(0, 100 - (10 * len(findings))),
        findings=findings,
    )


def _agent_evidence(conversation: Conversation) -> str:
    for message in conversation.messages:
        if message.role == "agent":
            return message.content
    return ""
