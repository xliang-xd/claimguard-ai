from __future__ import annotations

from dataclasses import dataclass

from claimguard.conversation import Conversation


@dataclass(frozen=True)
class RuleMatch:
    rule_id: str
    evidence: str


def run_rules(conversation: Conversation) -> list[RuleMatch]:
    matches: list[RuleMatch] = []
    customer_text = _joined_text(conversation, "customer")
    agent_text = _joined_text(conversation, "agent")

    if _has_claim_amount_dispute(customer_text) and _has_evasive_claim_answer(
        agent_text
    ):
        matches.append(RuleMatch("SEM-002", _first_agent_message(conversation)))

    if _has_impatient_tone(agent_text):
        matches.append(RuleMatch("SEM-003", _first_agent_message(conversation)))

    if _has_claim_amount_dispute(customer_text) and not _mentions_deductible_or_clause(
        agent_text
    ):
        matches.append(RuleMatch("RAG-001", _first_customer_message(conversation)))

    return matches


def _joined_text(conversation: Conversation, role: str) -> str:
    return " ".join(
        message.content for message in conversation.messages if message.role == role
    ).lower()


def _first_agent_message(conversation: Conversation) -> str:
    for message in conversation.messages:
        if message.role == "agent":
            return message.content
    return ""


def _first_customer_message(conversation: Conversation) -> str:
    for message in conversation.messages:
        if message.role == "customer":
            return message.content
    return ""


def _has_claim_amount_dispute(text: str) -> bool:
    return ("reimburse" in text or "claim" in text or "payout" in text) and (
        "why" in text or "only" in text
    )


def _has_evasive_claim_answer(text: str) -> bool:
    return "review team" in text or "final result" in text or "do not know" in text


def _has_impatient_tone(text: str) -> bool:
    return "final result" in text or "just like this" in text


def _mentions_deductible_or_clause(text: str) -> bool:
    return "deductible" in text or "clause" in text
