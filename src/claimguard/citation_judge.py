from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, Callable, Literal, Optional, Protocol
from urllib import request

from claimguard.agent_runtime.evidence import EvidenceRecord
from claimguard.config import load_project_environment


DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3.7-plus"
REQUEST_TIMEOUT_SECONDS = 30
CitationStatus = Literal["supported", "unsupported", "insufficient_evidence"]
_STATUSES = ("supported", "unsupported", "insufficient_evidence")
CitationReasonCode = Literal[
    "citation_supported", "citation_unsupported", "insufficient_evidence"
]
_REASON_CODES_BY_STATUS = {
    "supported": "citation_supported",
    "unsupported": "citation_unsupported",
    "insufficient_evidence": "insufficient_evidence",
}
_REASON_CODES = tuple(_REASON_CODES_BY_STATUS.values())
_VERDICT_FIELDS = ("status", "citations", "reason_code")
_MISSING_RESPONSE = object()


class CitationJudgeError(ValueError):
    """Raised when citation judging cannot produce a valid verdict."""


@dataclass(frozen=True)
class CitationVerdict:
    status: CitationStatus
    citations: tuple[str, ...]
    reason_code: CitationReasonCode


class CitationJudge(Protocol):
    def judge(
        self, draft: str, evidence: tuple[EvidenceRecord, ...]
    ) -> CitationVerdict:
        ...


Transport = Callable[[request.Request, int], Any]


class QwenCitationJudge:
    def __init__(self, transport: Optional[Transport] = None):
        load_project_environment()
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise CitationJudgeError("DASHSCOPE_API_KEY is required for citation judging")

        base_url = _read_non_empty_environment_value(
            "CLAIMGUARD_DASHSCOPE_BASE_URL", DEFAULT_BASE_URL
        )
        self.model = _read_non_empty_environment_value(
            "CLAIMGUARD_CITATION_MODEL", DEFAULT_MODEL
        )
        if not self.model.lower().startswith("qwen"):
            raise CitationJudgeError("Citation judge model must be a Qwen model")
        self._send = _build_sender(
            api_key,
            base_url.rstrip("/"),
            transport or request.urlopen,
        )

    def judge(
        self, draft: str, evidence: tuple[EvidenceRecord, ...]
    ) -> CitationVerdict:
        _validate_judge_input(draft, evidence)
        payload = {
            "model": self.model,
            "temperature": 0,
            "enable_thinking": False,
            "messages": [
                {"role": "system", "content": _SYSTEM_INSTRUCTION},
                {"role": "user", "content": _format_judge_input(draft, evidence)},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "citation_verdict",
                    "strict": True,
                    "schema": _response_schema(),
                },
            },
        }
        try:
            response = self._send(payload)
        except Exception:
            raise CitationJudgeError("Citation judge request failed") from None

        response_payload: object = _MISSING_RESPONSE
        try:
            with response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            raise CitationJudgeError("Citation judge response was invalid") from None
        if response_payload is _MISSING_RESPONSE:
            raise CitationJudgeError("Citation judge response was invalid")

        try:
            content = response_payload["choices"][0]["message"]["content"]
            verdict_payload = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            raise CitationJudgeError("Citation judge response was invalid") from None
        if not isinstance(content, str):
            raise CitationJudgeError("Citation judge response was invalid")

        return parse_citation_verdict(verdict_payload, evidence)


_SYSTEM_INSTRUCTION = """You are a citation judge for insurance policy replies.
Return exactly one JSON verdict. A supported verdict must cite one or more IDs from
the supplied evidence only. Unsupported and insufficient_evidence verdicts must not
contain citations. reason_code must be citation_supported for supported,
citation_unsupported for unsupported, and insufficient_evidence for
insufficient_evidence. Do not add fields."""


def parse_citation_verdict(
    payload: object, evidence: tuple[EvidenceRecord, ...]
) -> CitationVerdict:
    if not isinstance(payload, dict) or set(payload) != set(_VERDICT_FIELDS):
        raise CitationJudgeError("Citation judge response was invalid")

    status = payload["status"]
    citations = payload["citations"]
    reason_code = payload["reason_code"]
    if (
        status not in _STATUSES
        or not isinstance(citations, list)
        or any(not isinstance(citation, str) for citation in citations)
        or not isinstance(reason_code, str)
        or reason_code != _REASON_CODES_BY_STATUS.get(status)
    ):
        raise CitationJudgeError("Citation judge response was invalid")

    citation_ids = tuple(citations)
    allowed_ids = {record.clause_id for record in evidence}
    if status == "supported":
        if not citation_ids or any(citation not in allowed_ids for citation in citation_ids):
            raise CitationJudgeError("Citation judge response was invalid")
    elif citation_ids:
        raise CitationJudgeError("Citation judge response was invalid")

    return CitationVerdict(
        status=status,
        citations=citation_ids,
        reason_code=reason_code,
    )


def _read_non_empty_environment_value(name: str, default: str) -> str:
    value = os.getenv(name, default)
    if not isinstance(value, str) or not value.strip():
        raise CitationJudgeError("Citation judge configuration was invalid")
    return value.strip()


def _build_sender(
    api_key: str, base_url: str, transport: Transport
) -> Callable[[dict[str, object]], Any]:
    endpoint = f"{base_url}/chat/completions"

    def send(payload: dict[str, object]) -> Any:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        citation_request = request.Request(
            endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        return transport(citation_request, timeout=REQUEST_TIMEOUT_SECONDS)

    return send


def _validate_judge_input(draft: object, evidence: object) -> None:
    if not isinstance(draft, str) or not draft.strip():
        raise CitationJudgeError("Citation judge input was invalid")
    if not isinstance(evidence, tuple) or any(
        not isinstance(record, EvidenceRecord) for record in evidence
    ):
        raise CitationJudgeError("Citation judge input was invalid")


def _format_judge_input(draft: str, evidence: tuple[EvidenceRecord, ...]) -> str:
    lines = ["Draft:", draft, "Evidence:"]
    for record in evidence:
        lines.extend(
            (
                f"ID: {record.clause_id}",
                f"Title: {record.title}",
                f"Content: {record.content}",
            )
        )
    return "\n".join(lines)


def _response_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(_VERDICT_FIELDS),
        "properties": {
            "status": {"type": "string", "enum": list(_STATUSES)},
            "citations": {"type": "array", "items": {"type": "string"}},
            "reason_code": {"type": "string", "enum": list(_REASON_CODES)},
        },
        "oneOf": [
            {
                "properties": {
                    "status": {"type": "string", "enum": [status]},
                    "reason_code": {"type": "string", "enum": [reason_code]},
                }
            }
            for status, reason_code in _REASON_CODES_BY_STATUS.items()
        ],
    }
