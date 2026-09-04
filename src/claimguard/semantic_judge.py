from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, Callable, Optional, Protocol
from urllib import error, request

from claimguard.config import load_project_environment
from claimguard.conversation import Conversation


DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3.7-plus"
REQUEST_TIMEOUT_SECONDS = 30
ALLOWED_RULE_IDS = ("SEM-002", "SEM-003", "SEM-004", "SEM-005")
ALLOWED_CONFIDENCE = ("high", "medium", "low")
_JUDGMENT_FIELDS = (
    "rule_id",
    "violated",
    "evidence",
    "reasoning",
    "recommendation",
    "confidence",
)


class SemanticJudgeError(ValueError):
    """Raised when semantic judge configuration, requests, or responses are invalid."""


@dataclass(frozen=True)
class SemanticJudgment:
    rule_id: str
    violated: bool
    evidence: str
    reasoning: str
    recommendation: str
    confidence: str


class SemanticJudgeClient(Protocol):
    def judge(self, conversation: Conversation) -> list[SemanticJudgment]:
        ...


Transport = Callable[[request.Request, int], Any]


class DashScopeSemanticJudgeClient:
    def __init__(self, transport: Optional[Transport] = None):
        load_project_environment()
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise SemanticJudgeError("DASHSCOPE_API_KEY is required for semantic judging")

        base_url = _read_non_empty_environment_value(
            "CLAIMGUARD_DASHSCOPE_BASE_URL", DEFAULT_BASE_URL
        )
        self.model = _read_non_empty_environment_value(
            "CLAIMGUARD_SEMANTIC_MODEL", DEFAULT_MODEL
        )
        self._send = _build_sender(
            api_key,
            base_url.rstrip("/"),
            transport or request.urlopen,
        )

    def judge(self, conversation: Conversation) -> list[SemanticJudgment]:
        payload = {
            "model": self.model,
            "temperature": 0,
            "enable_thinking": False,
            "messages": [
                {"role": "system", "content": _SYSTEM_INSTRUCTION},
                {"role": "user", "content": _format_conversation(conversation)},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "semantic_judgments",
                    "strict": True,
                    "schema": _response_schema(),
                },
            },
        }
        try:
            with self._send(payload) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except (error.HTTPError, error.URLError, OSError):
            raise SemanticJudgeError("Semantic judge request failed") from None
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            raise SemanticJudgeError("Semantic judge response was invalid") from None

        return _parse_response(response_payload, conversation)


_SYSTEM_INSTRUCTION = """你是保险客服质检员。请只评估以下规则：
SEM-002：客服是否回应客户的核心问题；
SEM-003：客服是否表现出敷衍、不耐烦或轻视；
SEM-004：客户投诉时，客服是否承认并安抚客户的担忧；
SEM-005：客服是否对结果或时效作出无依据的确定性承诺。

必须为每条规则返回一个判断。若判定违规，evidence 必须是客服原话中的完整、逐字引用，且不得编造。若未违规，evidence、reasoning 和 recommendation 必须为空字符串。"""


def _response_schema() -> dict[str, object]:
    finding_schema: dict[str, object] = {
        "type": "object",
        "additionalProperties": False,
        "required": list(_JUDGMENT_FIELDS),
        "properties": {
            "rule_id": {"type": "string", "enum": list(ALLOWED_RULE_IDS)},
            "violated": {"type": "boolean"},
            "evidence": {"type": "string"},
            "reasoning": {"type": "string"},
            "recommendation": {"type": "string"},
            "confidence": {"type": "string", "enum": list(ALLOWED_CONFIDENCE)},
        },
    }
    required_rule_ids = [
        {
            "contains": {
                "type": "object",
                "required": ["rule_id"],
                "properties": {"rule_id": {"const": rule_id}},
            },
            "minContains": 1,
            "maxContains": 1,
        }
        for rule_id in ALLOWED_RULE_IDS
    ]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["findings"],
        "properties": {
            "findings": {
                "type": "array",
                "minItems": len(ALLOWED_RULE_IDS),
                "maxItems": len(ALLOWED_RULE_IDS),
                "items": finding_schema,
                "allOf": required_rule_ids,
            }
        },
    }


def _read_non_empty_environment_value(name: str, default: str) -> str:
    value = os.getenv(name, default)
    if not isinstance(value, str) or not value.strip():
        raise SemanticJudgeError(f"{name} must be a non-empty string")
    return value.strip()


def _build_sender(
    api_key: str, base_url: str, transport: Transport
) -> Callable[[dict[str, object]], Any]:
    endpoint = f"{base_url}/chat/completions"

    def send(payload: dict[str, object]) -> Any:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        semantic_request = request.Request(
            endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        return transport(semantic_request, timeout=REQUEST_TIMEOUT_SECONDS)

    return send


def _format_conversation(conversation: Conversation) -> str:
    lines = [f"会话编号：{conversation.id}", f"场景：{conversation.scenario}", "对话："]
    role_names = {"customer": "客户", "agent": "客服"}
    for message in conversation.messages:
        lines.append(f"{role_names.get(message.role, message.role)}：{message.content}")
    return "\n".join(lines)


def _parse_response(
    response_payload: object, conversation: Conversation
) -> list[SemanticJudgment]:
    try:
        content = response_payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise SemanticJudgeError("Semantic judge response was invalid") from None
    if not isinstance(content, str):
        raise SemanticJudgeError("Semantic judge response was invalid")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        raise SemanticJudgeError("Semantic judge response was invalid") from None
    return _parse_judgments(payload, conversation)


def _parse_judgments(payload: object, conversation: Conversation) -> list[SemanticJudgment]:
    if not isinstance(payload, dict) or set(payload) != {"findings"}:
        raise SemanticJudgeError("Semantic judge response was invalid")
    findings = payload["findings"]
    if not isinstance(findings, list) or len(findings) != len(ALLOWED_RULE_IDS):
        raise SemanticJudgeError("Semantic judge response was invalid")

    agent_messages = [
        message.content for message in conversation.messages if message.role == "agent"
    ]
    judgments: list[SemanticJudgment] = []
    seen_rule_ids: set[str] = set()
    for finding in findings:
        judgment = _parse_judgment(finding, agent_messages)
        if judgment.rule_id in seen_rule_ids:
            raise SemanticJudgeError("Semantic judge response was invalid")
        seen_rule_ids.add(judgment.rule_id)
        judgments.append(judgment)

    if seen_rule_ids != set(ALLOWED_RULE_IDS):
        raise SemanticJudgeError("Semantic judge response was invalid")
    return judgments


def _parse_judgment(finding: object, agent_messages: list[str]) -> SemanticJudgment:
    if not isinstance(finding, dict) or set(finding) != set(_JUDGMENT_FIELDS):
        raise SemanticJudgeError("Semantic judge response was invalid")

    rule_id = finding["rule_id"]
    violated = finding["violated"]
    evidence = finding["evidence"]
    reasoning = finding["reasoning"]
    recommendation = finding["recommendation"]
    confidence = finding["confidence"]
    if (
        rule_id not in ALLOWED_RULE_IDS
        or type(violated) is not bool
        or not all(isinstance(value, str) for value in (evidence, reasoning, recommendation))
        or confidence not in ALLOWED_CONFIDENCE
    ):
        raise SemanticJudgeError("Semantic judge response was invalid")

    if violated:
        if (
            not evidence.strip()
            or not reasoning.strip()
            or not recommendation.strip()
            or evidence not in agent_messages
        ):
            raise SemanticJudgeError("Semantic judge response was invalid")
    elif evidence or reasoning or recommendation:
        raise SemanticJudgeError("Semantic judge response was invalid")

    return SemanticJudgment(
        rule_id=rule_id,
        violated=violated,
        evidence=evidence,
        reasoning=reasoning,
        recommendation=recommendation,
        confidence=confidence,
    )
