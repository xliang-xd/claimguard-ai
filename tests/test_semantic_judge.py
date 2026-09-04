import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.conversation import Conversation, Message
from claimguard.semantic_judge import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DashScopeSemanticJudgeClient,
    SemanticJudgeError,
    SemanticJudgment,
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


class SemanticJudgeClientTest(unittest.TestCase):
    def setUp(self):
        self.conversation = Conversation(
            id="semantic-judge-test",
            scenario="Customer disputes a delayed claim payment.",
            messages=[
                Message(role="customer", content="我的理赔款为什么还没到账？"),
                Message(role="agent", content="您的理赔将在明天到账。"),
            ],
            expected_risks=[],
        )

    def test_posts_one_strict_schema_request_for_semantic_rules(self):
        transport = OneShotTransport(self._valid_response())
        client = self._client(transport)

        judgments = client.judge(self.conversation)

        self.assertEqual(len(transport.requests), 1)
        request, timeout = transport.requests[0]
        self.assertEqual(request.full_url, f"{DEFAULT_BASE_URL}/chat/completions")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(timeout, 30)
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "qwen3.7-plus")
        self.assertEqual(payload["temperature"], 0)
        self.assertFalse(payload["enable_thinking"])
        self.assertEqual(payload["response_format"]["type"], "json_schema")
        self.assertTrue(payload["response_format"]["json_schema"]["strict"])
        schema = payload["response_format"]["json_schema"]["schema"]
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["required"], ["findings"])
        self.assertEqual(schema["properties"]["findings"]["minItems"], 4)
        self.assertEqual(schema["properties"]["findings"]["maxItems"], 4)
        finding_schema = schema["properties"]["findings"]["items"]
        self.assertFalse(finding_schema["additionalProperties"])
        self.assertEqual(
            finding_schema["properties"]["rule_id"]["enum"],
            ["SEM-002", "SEM-003", "SEM-004", "SEM-005"],
        )
        self.assertIn("客服原话", payload["messages"][0]["content"])
        self.assertEqual(
            judgments[-1],
            SemanticJudgment(
                rule_id="SEM-005",
                violated=True,
                evidence="您的理赔将在明天到账。",
                reasoning="客服作出了没有依据的到账承诺。",
                recommendation="说明到账时间需以审核结果为准。",
                confidence="high",
            ),
        )

    def test_uses_configured_semantic_model(self):
        transport = OneShotTransport(self._valid_response())
        client = self._client(transport, CLAIMGUARD_SEMANTIC_MODEL="local-semantic-model")

        client.judge(self.conversation)

        payload = json.loads(transport.requests[0][0].data.decode("utf-8"))
        self.assertEqual(payload["model"], "local-semantic-model")

    def test_parses_a_complete_valid_response(self):
        client = self._client(OneShotTransport(self._valid_response()))

        judgments = client.judge(self.conversation)

        self.assertEqual([judgment.rule_id for judgment in judgments], [
            "SEM-002",
            "SEM-003",
            "SEM-004",
            "SEM-005",
        ])
        self.assertEqual(judgments[0].confidence, "medium")
        self.assertFalse(judgments[0].violated)

    def test_rejects_duplicate_or_unsupported_semantic_rule_ids(self):
        duplicate = self._findings()
        duplicate[-1]["rule_id"] = "SEM-004"
        unsupported = self._findings()
        unsupported[-1]["rule_id"] = "SEM-999"

        for findings in (duplicate, unsupported):
            with self.subTest(findings=findings):
                client = self._client(OneShotTransport(self._response(findings)))
                with self.assertRaises(SemanticJudgeError):
                    client.judge(self.conversation)

    def test_rejects_incomplete_or_malformed_model_content(self):
        malformed = {"choices": [{"message": {"content": "not json"}}]}
        missing_rule = self._findings()[:-1]
        missing_field = self._findings()
        del missing_field[0]["confidence"]

        for response in (malformed, self._response(missing_rule), self._response(missing_field)):
            with self.subTest(response=response):
                client = self._client(OneShotTransport(response))
                with self.assertRaises(SemanticJudgeError):
                    client.judge(self.conversation)

    def test_rejects_invalid_judgment_values_and_ungrounded_evidence(self):
        invalid_confidence = self._findings()
        invalid_confidence[0]["confidence"] = "certain"
        non_boolean = self._findings()
        non_boolean[0]["violated"] = 1
        ungrounded_evidence = self._findings()
        ungrounded_evidence[-1]["evidence"] = "我们会马上处理。"
        non_violation_text = self._findings()
        non_violation_text[0]["reasoning"] = "不应出现"
        blank_violation_text = self._findings()
        blank_violation_text[-1]["recommendation"] = " "
        extra_field = self._findings()
        extra_field[0]["unexpected"] = "not allowed"

        for findings in (
            invalid_confidence,
            non_boolean,
            ungrounded_evidence,
            non_violation_text,
            blank_violation_text,
            extra_field,
        ):
            with self.subTest(findings=findings):
                client = self._client(OneShotTransport(self._response(findings)))
                with self.assertRaises(SemanticJudgeError):
                    client.judge(self.conversation)

    def test_rejects_evidence_that_is_only_a_fragment_of_an_agent_message(self):
        findings = self._findings()
        findings[-1]["evidence"] = "将在明天到账。"
        client = self._client(OneShotTransport(self._response(findings)))

        with self.assertRaises(SemanticJudgeError):
            client.judge(self.conversation)

    def test_http_failure_does_not_disclose_authorization_value(self):
        def failing_transport(request, timeout):
            raise HTTPError(request.full_url, 503, "unavailable", None, None)

        client = self._client(failing_transport)

        with self.assertRaises(SemanticJudgeError) as context:
            client.judge(self.conversation)

        self.assertNotIn("offline-semantic-credential", str(context.exception))
        self.assertNotIn("Bearer", str(context.exception))

    def test_url_and_os_failures_are_credential_safe_semantic_judge_errors(self):
        def url_failure(request, timeout):
            raise URLError("offline transport failure")

        def os_failure(request, timeout):
            raise OSError("offline socket failure")

        for failing_transport in (url_failure, os_failure):
            with self.subTest(transport=failing_transport.__name__):
                client = self._client(failing_transport)
                with self.assertRaises(SemanticJudgeError) as context:
                    client.judge(self.conversation)

                self.assertEqual(str(context.exception), "Semantic judge request failed")
                self.assertNotIn("offline-semantic-credential", str(context.exception))
                self.assertNotIn("Bearer", str(context.exception))

    def test_invalid_utf8_response_bytes_are_a_credential_safe_semantic_judge_error(self):
        client = self._client(OneShotTransport(b"\xff"))

        with self.assertRaises(SemanticJudgeError) as context:
            client.judge(self.conversation)

        self.assertEqual(str(context.exception), "Semantic judge response was invalid")
        self.assertNotIn("offline-semantic-credential", str(context.exception))
        self.assertNotIn("Bearer", str(context.exception))

    def test_missing_api_key_raises_before_a_request_is_made(self):
        transport = OneShotTransport(self._valid_response())
        with patch.dict(os.environ, {}, clear=True):
            with patch("claimguard.semantic_judge.load_project_environment"):
                with self.assertRaises(SemanticJudgeError):
                    DashScopeSemanticJudgeClient(transport=transport)

        self.assertEqual(transport.requests, [])

    def _client(self, transport, **environment):
        values = {"DASHSCOPE_API_KEY": "offline-semantic-credential"}
        values.update(environment)
        with patch.dict(os.environ, values, clear=True):
            with patch("claimguard.semantic_judge.load_project_environment"):
                return DashScopeSemanticJudgeClient(transport=transport)

    def _findings(self):
        return [
            {
                "rule_id": "SEM-002",
                "violated": False,
                "evidence": "",
                "reasoning": "",
                "recommendation": "",
                "confidence": "medium",
            },
            {
                "rule_id": "SEM-003",
                "violated": False,
                "evidence": "",
                "reasoning": "",
                "recommendation": "",
                "confidence": "low",
            },
            {
                "rule_id": "SEM-004",
                "violated": False,
                "evidence": "",
                "reasoning": "",
                "recommendation": "",
                "confidence": "high",
            },
            {
                "rule_id": "SEM-005",
                "violated": True,
                "evidence": "您的理赔将在明天到账。",
                "reasoning": "客服作出了没有依据的到账承诺。",
                "recommendation": "说明到账时间需以审核结果为准。",
                "confidence": "high",
            },
        ]

    def _response(self, findings):
        return {"choices": [{"message": {"content": json.dumps({"findings": findings})}}]}

    def _valid_response(self):
        return self._response(self._findings())


if __name__ == "__main__":
    unittest.main()
