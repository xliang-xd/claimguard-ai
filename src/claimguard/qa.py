from __future__ import annotations

from dataclasses import asdict, dataclass

from claimguard.conversation import Conversation
from claimguard.rule_runner import run_rules
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
            )
        )

    return QAReport(
        conversation_id=conversation.id,
        scenario=conversation.scenario,
        score=max(0, 100 - (10 * len(findings))),
        findings=findings,
    )
