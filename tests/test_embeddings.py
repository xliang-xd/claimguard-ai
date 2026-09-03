import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.embeddings import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DashScopeEmbeddingClient,
    EmbeddingError,
)


def fake_environment(name, default=None):
    values = {
        "DASHSCOPE_API_KEY": "offline-test-credential",
        "CLAIMGUARD_EMBEDDING_DIMENSIONS": "2",
    }
    return values.get(name, default)


class OneShotResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class OneShotTransport:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        return OneShotResponse(self.payload)


class EmbeddingClientTest(unittest.TestCase):
    def test_missing_key_raises_before_a_request_is_made(self):
        transport = OneShotTransport({})

        with patch("claimguard.embeddings.os.getenv", return_value=None):
            with self.assertRaises(EmbeddingError):
                DashScopeEmbeddingClient(transport=transport)

        self.assertEqual(transport.requests, [])

    def test_parses_embeddings_in_response_index_order(self):
        transport = OneShotTransport(
            {
                "object": "list",
                "data": [
                    {"object": "embedding", "index": 1, "embedding": [0.0, 1.0]},
                    {"object": "embedding", "index": 0, "embedding": [1.0, 0.0]},
                ],
                "model": DEFAULT_MODEL,
                "usage": {"prompt_tokens": 2, "total_tokens": 2},
            }
        )

        with patch("claimguard.embeddings.os.getenv", side_effect=fake_environment):
            vectors = DashScopeEmbeddingClient(transport=transport).embed(["first", "second"])

        self.assertEqual(vectors, [[1.0, 0.0], [0.0, 1.0]])
        request, timeout = transport.requests[0]
        self.assertEqual(request.full_url, f"{DEFAULT_BASE_URL}/embeddings")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(timeout, 30)
        self.assertEqual(
            json.loads(request.data.decode("utf-8")),
            {
                "model": DEFAULT_MODEL,
                "input": ["first", "second"],
                "dimensions": 2,
                "encoding_format": "float",
            },
        )

    def test_http_failure_does_not_disclose_authorization_value(self):
        def failing_transport(request, timeout):
            raise HTTPError(request.full_url, 503, "unavailable", None, None)

        with patch("claimguard.embeddings.os.getenv", side_effect=fake_environment):
            client = DashScopeEmbeddingClient(transport=failing_transport)
            with self.assertRaises(EmbeddingError) as context:
                client.embed(["claim text"])

        self.assertNotIn("offline-test-credential", str(context.exception))

    def test_rejects_response_that_omits_an_input_embedding(self):
        transport = OneShotTransport(
            {
                "object": "list",
                "data": [
                    {"object": "embedding", "index": 0, "embedding": [1.0, 0.0]}
                ],
                "model": DEFAULT_MODEL,
                "usage": {"prompt_tokens": 2, "total_tokens": 2},
            }
        )

        with patch("claimguard.embeddings.os.getenv", side_effect=fake_environment):
            client = DashScopeEmbeddingClient(transport=transport)
            with self.assertRaises(EmbeddingError):
                client.embed(["first", "second"])


if __name__ == "__main__":
    unittest.main()
