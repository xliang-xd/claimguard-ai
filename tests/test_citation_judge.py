import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.agent_runtime.evidence import EvidenceRecord
from claimguard.citation_judge import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    CitationJudgeError,
    CitationVerdict,
    QwenCitationJudge,
    parse_citation_verdict,
)


DRAFT = "客服草稿：等待期内不予赔付。"
EVIDENCE_CONTENT = "条款正文：等待期内疾病治疗不予赔付。"
SOURCE_URL = "https://policy.example.test/private"
CREDENTIAL = "offline-citation-credential"
URL_SECRET = "url-secret"


def evidence_records():
    return (
        EvidenceRecord(
            clause_id="18",
            title="等待期",
            content=EVIDENCE_CONTENT,
            source_path=SOURCE_URL,
            retrieval_score=0.8,
            rerank_score=0.9,
        ),
        EvidenceRecord(
            clause_id="19",
            title="除外责任",
            content="条款正文：既往症不予赔付。",
            source_path="policy.md",
            retrieval_score=0.7,
            rerank_score=0.8,
        ),
    )


class OneShotResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        if isinstance(self.payload, bytes):
            return self.payload
        return json.dumps(self.payload).encode("utf-8")


class OneShotTransport:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        return OneShotResponse(self.payload)


class SuppressingReadFailureResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return True

    def read(self):
        raise RuntimeError(DRAFT)


class CitationVerdictTest(unittest.TestCase):
    def test_supported_requires_existing_citation(self):
        verdict = parse_citation_verdict(
            {
                "status": "supported",
                "citations": ["18"],
                "reason_code": "citation_supported",
            },
            evidence_records(),
        )

        self.assertEqual(
            verdict,
            CitationVerdict(
                status="supported",
                citations=("18",),
                reason_code="citation_supported",
            ),
        )

    def test_unknown_or_missing_citation_is_rejected(self):
        invalid_verdicts = (
            {
                "status": "supported",
                "citations": ["999"],
                "reason_code": "citation_supported",
            },
            {
                "status": "supported",
                "citations": [],
                "reason_code": "citation_supported",
            },
        )

        for payload in invalid_verdicts:
            with self.subTest(payload=payload):
                with self.assertRaises(CitationJudgeError):
                    parse_citation_verdict(payload, evidence_records())

    def test_non_supported_statuses_require_no_citations(self):
        reason_codes = {
            "unsupported": "citation_unsupported",
            "insufficient_evidence": "insufficient_evidence",
        }
        for status, reason_code in reason_codes.items():
            with self.subTest(status=status):
                verdict = parse_citation_verdict(
                    {"status": status, "citations": [], "reason_code": reason_code},
                    evidence_records(),
                )

                self.assertEqual(verdict.status, status)
                self.assertEqual(verdict.citations, ())

    def test_non_supported_statuses_reject_citations(self):
        reason_codes = {
            "unsupported": "citation_unsupported",
            "insufficient_evidence": "insufficient_evidence",
        }
        for status, reason_code in reason_codes.items():
            with self.subTest(status=status):
                with self.assertRaises(CitationJudgeError):
                    parse_citation_verdict(
                        {"status": status, "citations": ["18"], "reason_code": reason_code},
                        evidence_records(),
                    )

    def test_rejects_arbitrary_reason_codes(self):
        invalid_verdicts = (
            {"status": "supported", "citations": ["18"], "reason_code": "x"},
            {
                "status": "unsupported",
                "citations": [],
                "reason_code": "not_grounded",
            },
            {
                "status": "insufficient_evidence",
                "citations": [],
                "reason_code": "need_more_information",
            },
        )

        for payload in invalid_verdicts:
            with self.subTest(payload=payload):
                with self.assertRaises(CitationJudgeError):
                    parse_citation_verdict(payload, evidence_records())

    def test_rejects_reason_codes_that_do_not_match_status(self):
        invalid_verdicts = (
            {
                "status": "supported",
                "citations": ["18"],
                "reason_code": "citation_unsupported",
            },
            {
                "status": "unsupported",
                "citations": [],
                "reason_code": "insufficient_evidence",
            },
            {
                "status": "insufficient_evidence",
                "citations": [],
                "reason_code": "citation_supported",
            },
        )

        for payload in invalid_verdicts:
            with self.subTest(payload=payload):
                with self.assertRaises(CitationJudgeError):
                    parse_citation_verdict(payload, evidence_records())

    def test_rejects_non_strict_or_invalid_verdict_shape(self):
        invalid_verdicts = (
            {"status": "supported", "citations": ["18"]},
            {
                "status": "supported",
                "citations": ["18"],
                "reason_code": "citation_supported",
                "extra": "not allowed",
            },
            {"status": "unknown", "citations": [], "reason_code": "citation_supported"},
            {"status": "supported", "citations": "18", "reason_code": "citation_supported"},
            {"status": "supported", "citations": [18], "reason_code": "citation_supported"},
            {"status": "supported", "citations": ["18"], "reason_code": 1},
        )

        for payload in invalid_verdicts:
            with self.subTest(payload=payload):
                with self.assertRaises(CitationJudgeError):
                    parse_citation_verdict(payload, evidence_records())


class QwenCitationJudgeTest(unittest.TestCase):
    def test_posts_one_strict_qwen_request_and_parses_verdict(self):
        transport = OneShotTransport(self._response("supported", ["18"]))
        judge = self._judge(transport)

        verdict = judge.judge(DRAFT, evidence_records())

        self.assertEqual(
            verdict,
            CitationVerdict(
                status="supported",
                citations=("18",),
                reason_code="citation_supported",
            ),
        )
        self.assertEqual(len(transport.requests), 1)
        request, timeout = transport.requests[0]
        self.assertEqual(request.full_url, f"{DEFAULT_BASE_URL}/chat/completions")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(timeout, 30)
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], DEFAULT_MODEL)
        self.assertTrue(payload["model"].lower().startswith("qwen"))
        self.assertEqual(payload["temperature"], 0)
        self.assertFalse(payload["enable_thinking"])
        self.assertEqual(payload["response_format"]["type"], "json_schema")
        self.assertTrue(payload["response_format"]["json_schema"]["strict"])
        schema = payload["response_format"]["json_schema"]["schema"]
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["required"], ["status", "citations", "reason_code"])
        self.assertEqual(
            schema["properties"]["status"]["enum"],
            ["supported", "unsupported", "insufficient_evidence"],
        )
        self.assertEqual(
            schema["properties"]["reason_code"]["enum"],
            ["citation_supported", "citation_unsupported", "insufficient_evidence"],
        )
        self.assertIn(DRAFT, payload["messages"][1]["content"])
        self.assertIn(EVIDENCE_CONTENT, payload["messages"][1]["content"])
        self.assertIn("18", payload["messages"][1]["content"])

    def test_rejects_a_non_qwen_configured_model_before_request(self):
        transport = OneShotTransport(self._response("supported", ["18"]))

        with self._environment(CLAIMGUARD_CITATION_MODEL="gpt-5"):
            with patch("claimguard.citation_judge.load_project_environment"):
                with self.assertRaises(CitationJudgeError) as context:
                    QwenCitationJudge(transport=transport)

        self.assertEqual(str(context.exception), "Citation judge model must be a Qwen model")
        self.assertEqual(transport.requests, [])

    def test_request_failures_do_not_disclose_sensitive_input(self):
        def http_failure(request, timeout):
            raise HTTPError(request.full_url, 503, "unavailable", None, None)

        def url_failure(request, timeout):
            raise URLError("offline transport failure")

        def os_failure(request, timeout):
            raise OSError("offline socket failure")

        for transport in (http_failure, url_failure, os_failure):
            with self.subTest(transport=transport.__name__):
                judge = self._judge(
                    transport,
                    CLAIMGUARD_DASHSCOPE_BASE_URL="https://offline.example/?token=url-secret",
                )
                with self.assertRaises(CitationJudgeError) as context:
                    judge.judge(DRAFT, evidence_records())

                self.assertEqual(str(context.exception), "Citation judge request failed")
                self._assert_sensitive_values_hidden(str(context.exception))

    def test_invalid_responses_do_not_disclose_sensitive_input(self):
        for response in (
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                f"not json {DRAFT} {EVIDENCE_CONTENT} "
                                f"{SOURCE_URL} {CREDENTIAL}"
                            )
                        }
                    }
                ]
            },
            b"\xff",
            self._response("supported", ["999"]),
        ):
            with self.subTest(response=response):
                judge = self._judge(OneShotTransport(response))
                with self.assertRaises(CitationJudgeError) as context:
                    judge.judge(DRAFT, evidence_records())

                self.assertEqual(str(context.exception), "Citation judge response was invalid")
                self._assert_sensitive_values_hidden(str(context.exception))

    def test_suppressed_response_read_failure_is_not_treated_as_a_verdict(self):
        judge = self._judge(lambda request, timeout: SuppressingReadFailureResponse())

        with self.assertRaises(CitationJudgeError) as context:
            judge.judge(DRAFT, evidence_records())

        self.assertEqual(str(context.exception), "Citation judge response was invalid")
        self._assert_sensitive_values_hidden(str(context.exception))

    def test_missing_api_key_raises_before_a_request_is_made(self):
        transport = OneShotTransport(self._response("supported", ["18"]))
        with patch.dict(os.environ, {}, clear=True):
            with patch("claimguard.citation_judge.load_project_environment"):
                with self.assertRaises(CitationJudgeError):
                    QwenCitationJudge(transport=transport)

        self.assertEqual(transport.requests, [])

    def _judge(self, transport, **environment):
        with self._environment(**environment):
            with patch("claimguard.citation_judge.load_project_environment"):
                return QwenCitationJudge(transport=transport)

    def _environment(self, **environment):
        values = {"DASHSCOPE_API_KEY": CREDENTIAL}
        values.update(environment)
        return patch.dict(os.environ, values, clear=True)

    def _response(self, status, citations):
        verdict = {
            "status": status,
            "citations": citations,
            "reason_code": {
                "supported": "citation_supported",
                "unsupported": "citation_unsupported",
                "insufficient_evidence": "insufficient_evidence",
            }[status],
        }
        return {"choices": [{"message": {"content": json.dumps(verdict)}}]}

    def _assert_sensitive_values_hidden(self, message):
        for value in (DRAFT, EVIDENCE_CONTENT, SOURCE_URL, CREDENTIAL, URL_SECRET):
            self.assertNotIn(value, message)


if __name__ == "__main__":
    unittest.main()
