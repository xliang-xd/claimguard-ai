import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.reranking import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    QwenReranker,
    RerankingError,
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


class ReadFailureResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        raise RuntimeError("客户私密问题：条款私密正文")


class SuppressingReadFailureResponse(ReadFailureResponse):
    def __exit__(self, exc_type, exc_value, traceback):
        return True


class QwenRerankerTest(unittest.TestCase):
    def test_qwen_reranker_posts_model_query_and_documents(self):
        transport = OneShotTransport(self._response([(0, 0.8)]))
        client = self._client(transport)

        self.assertEqual(client.rerank("等待期", ["条款一"]), [0.8])

        request, timeout = transport.requests[0]
        self.assertEqual(request.full_url, f"{DEFAULT_BASE_URL}/reranks")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(timeout, 30)
        self.assertEqual(
            json.loads(request.data.decode("utf-8")),
            {"model": DEFAULT_MODEL, "query": "等待期", "documents": ["条款一"]},
        )

    def test_qwen_reranker_returns_scores_in_document_order(self):
        transport = OneShotTransport(self._response([(1, 0.1), (0, 0.9)]))
        client = self._client(transport)

        self.assertEqual(client.rerank("查询", ["甲", "乙"]), [0.9, 0.1])

    def test_qwen_reranker_uses_configured_model_and_base_url(self):
        transport = OneShotTransport(self._response([(0, 0.8)]))
        client = self._client(
            transport,
            CLAIMGUARD_RERANK_MODEL="configured-reranker",
            CLAIMGUARD_DASHSCOPE_BASE_URL="https://offline.example/qwen/",
        )

        client.rerank("等待期", ["条款一"])

        request, _ = transport.requests[0]
        self.assertEqual(client.model, "configured-reranker")
        self.assertEqual(request.full_url, "https://offline.example/qwen/reranks")

    def test_qwen_reranker_hides_authorization_on_http_error(self):
        def failing_transport(request, timeout):
            raise HTTPError(request.full_url, 503, "unavailable", None, None)

        client = self._client(
            failing_transport,
            CLAIMGUARD_DASHSCOPE_BASE_URL="https://offline.example/reranks?token=url-secret",
        )

        with self.assertRaisesRegex(RerankingError, "Reranking request failed") as context:
            client.rerank("客户私密问题", ["条款私密正文"])

        error_text = str(context.exception)
        self.assertNotIn("offline-reranking-credential", error_text)
        self.assertNotIn("Bearer", error_text)
        self.assertNotIn("url-secret", error_text)
        self.assertNotIn("客户私密问题", error_text)
        self.assertNotIn("条款私密正文", error_text)

    def test_qwen_reranker_hides_details_on_url_and_os_errors(self):
        def url_failure(request, timeout):
            raise URLError("offline transport failure")

        def os_failure(request, timeout):
            raise OSError("offline socket failure")

        for failing_transport in (url_failure, os_failure):
            with self.subTest(transport=failing_transport.__name__):
                client = self._client(failing_transport)

                with self.assertRaises(RerankingError) as context:
                    client.rerank("客户私密问题", ["条款私密正文"])

                self.assertEqual(str(context.exception), "Reranking request failed")
                self.assertNotIn("offline-reranking-credential", str(context.exception))
                self.assertNotIn("客户私密问题", str(context.exception))

    def test_qwen_reranker_hides_details_on_invalid_response(self):
        client = self._client(OneShotTransport(b"\xff"))

        with self.assertRaises(RerankingError) as context:
            client.rerank("客户私密问题", ["条款私密正文"])

        error_text = str(context.exception)
        self.assertEqual(error_text, "Reranking response was invalid")
        self.assertNotIn("offline-reranking-credential", error_text)
        self.assertNotIn("客户私密问题", error_text)
        self.assertNotIn("条款私密正文", error_text)

    def test_qwen_reranker_hides_details_when_response_read_fails(self):
        client = self._client(lambda request, timeout: ReadFailureResponse())

        with self.assertRaises(RerankingError) as context:
            client.rerank("客户私密问题", ["条款私密正文"])

        error_text = str(context.exception)
        self.assertEqual(error_text, "Reranking response was invalid")
        self.assertNotIn("客户私密问题", error_text)
        self.assertNotIn("条款私密正文", error_text)

    def test_qwen_reranker_hides_details_when_response_exit_suppresses_read_failure(self):
        client = self._client(
            lambda request, timeout: SuppressingReadFailureResponse()
        )

        with self.assertRaises(RerankingError) as context:
            client.rerank("客户私密问题", ["条款私密正文"])

        error_text = str(context.exception)
        self.assertEqual(error_text, "Reranking response was invalid")
        self.assertNotIn("客户私密问题", error_text)
        self.assertNotIn("条款私密正文", error_text)

    def test_qwen_reranker_rejects_incomplete_or_invalid_response(self):
        responses = [
            {},
            self._response([(0, 0.8)]),
            self._response([(0, True), (1, 0.2)]),
            self._response([(0, float("nan")), (1, 0.2)]),
            self._response([(0, 0.8), (0, 0.2)]),
            self._response([(0, 0.8), (2, 0.2)]),
        ]
        for response in responses:
            with self.subTest(response=response):
                client = self._client(OneShotTransport(response))
                with self.assertRaisesRegex(RerankingError, "response was invalid"):
                    client.rerank("查询", ["甲", "乙"])

    def test_qwen_reranker_rejects_invalid_input_without_request(self):
        transport = OneShotTransport(self._response([(0, 0.8)]))
        client = self._client(transport)

        for query, documents in (("", ["条款"]), ("查询", []), ("查询", [" "])):
            with self.subTest(query=query, documents=documents):
                with self.assertRaises(RerankingError):
                    client.rerank(query, documents)

        self.assertEqual(transport.requests, [])

    def test_missing_api_key_raises_before_a_request_is_made(self):
        transport = OneShotTransport(self._response([(0, 0.8)]))
        with patch.dict(os.environ, {}, clear=True):
            with patch("claimguard.reranking.load_project_environment"):
                with self.assertRaises(RerankingError):
                    QwenReranker(transport=transport)

        self.assertEqual(transport.requests, [])

    def _client(self, transport, **environment):
        values = {"DASHSCOPE_API_KEY": "offline-reranking-credential"}
        values.update(environment)
        with patch.dict(os.environ, values, clear=True):
            with patch("claimguard.reranking.load_project_environment"):
                return QwenReranker(transport=transport)

    def _response(self, results):
        return {
            "output": {
                "results": [
                    {"index": index, "relevance_score": score}
                    for index, score in results
                ]
            }
        }


if __name__ == "__main__":
    unittest.main()
