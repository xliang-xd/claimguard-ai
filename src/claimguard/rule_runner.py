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

    if _has_chinese_deductible_dispute(customer_text) and _lacks_deductible_explanation(
        agent_text
    ):
        matches.append(RuleMatch("RAG-001", _first_customer_message(conversation)))

    if _has_waiting_period_denial_question(
        customer_text
    ) and _lacks_waiting_period_explanation(agent_text):
        matches.append(RuleMatch("RAG-002", _first_customer_message(conversation)))

    if _has_denial_citation_question(
        customer_text
    ) and _lacks_clause_citation(agent_text):
        matches.append(RuleMatch("RAG-005", _first_customer_message(conversation)))
    elif _has_coverage_denial_question(
        customer_text
    ) and _lacks_coverage_explanation(agent_text):
        matches.append(RuleMatch("RAG-003", _first_customer_message(conversation)))

    if _has_accident_definition_question(
        customer_text
    ) and _lacks_accident_definition(agent_text):
        matches.append(RuleMatch("RAG-004", _first_customer_message(conversation)))

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


def _has_chinese_deductible_dispute(text: str) -> bool:
    return _contains_all(text, ("为什么", "理赔")) and _contains_any(
        text, ("只赔", "赔得少", "少赔")
    )


def _lacks_deductible_explanation(text: str) -> bool:
    return not (
        "免赔额" in text and _contains_any(text, ("扣除", "先扣", "扣掉"))
    )


def _has_waiting_period_denial_question(text: str) -> bool:
    return _contains_all(text, ("为什么", "等待期")) and _contains_any(
        text, ("不赔", "拒赔", "不予赔付")
    )


def _lacks_waiting_period_explanation(text: str) -> bool:
    return not (
        _contains_all(text, ("等待期内", "疾病治疗"))
        and _contains_any(text, ("不予赔付", "不赔", "拒赔"))
    )


def _has_coverage_denial_question(text: str) -> bool:
    return "为什么" in text and _contains_any(text, ("疾病", "皮肤病", "病症")) and _contains_any(
        text, ("保障范围", "不在保障", "不能理赔", "不能赔")
    )


def _lacks_coverage_explanation(text: str) -> bool:
    return not (
        _contains_any(text, ("疾病保障清单", "列入疾病"))
        and _contains_any(text, ("可以申请", "才可以", "可申请", "赔付"))
    )


def _has_accident_definition_question(text: str) -> bool:
    return "意外事故" in text and _contains_any(text, ("怎么定义", "具体定义", "算不算"))


def _lacks_accident_definition(text: str) -> bool:
    return not _contains_all(text, ("突发", "外来", "非故意", "直接导致"))


def _has_denial_citation_question(text: str) -> bool:
    return _contains_any(text, ("依据哪条保单条款", "依据哪条条款", "引用哪条条款")) and _contains_any(
        text, ("拒赔", "不赔", "不能赔")
    )


def _lacks_clause_citation(text: str) -> bool:
    return not (
        _contains_any(text, ("条款24", "条款 24"))
        and not _lacks_coverage_explanation(text)
    )


def _contains_all(text: str, phrases: tuple[str, ...]) -> bool:
    return all(phrase in text for phrase in phrases)


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)
