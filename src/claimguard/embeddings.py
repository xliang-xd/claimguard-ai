from __future__ import annotations

import json
import math
import os
from typing import Any, Callable, Optional, Protocol
from urllib import error, request

from claimguard.config import load_project_environment


DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3.7-text-embedding"
DEFAULT_DIMENSIONS = 1024
REQUEST_TIMEOUT_SECONDS = 30


class EmbeddingError(ValueError):
    """Raised when embedding configuration, requests, or responses are invalid."""


class EmbeddingClient(Protocol):
    model: str

    def embed(self, texts: list[str]) -> list[list[float]]:
        ...


Transport = Callable[[request.Request, int], Any]


class DashScopeEmbeddingClient:
    def __init__(self, transport: Optional[Transport] = None):
        load_project_environment()
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise EmbeddingError("DASHSCOPE_API_KEY is required for embeddings")

        base_url = _read_non_empty_environment_value(
            "CLAIMGUARD_DASHSCOPE_BASE_URL", DEFAULT_BASE_URL
        )
        self.model = _read_non_empty_environment_value(
            "CLAIMGUARD_EMBEDDING_MODEL", DEFAULT_MODEL
        )
        self.dimensions = _read_dimensions()
        self._send = _build_sender(
            api_key,
            base_url.rstrip("/"),
            transport or request.urlopen,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        _validate_texts(texts)
        payload = {
            "model": self.model,
            "input": texts,
            "dimensions": self.dimensions,
            "encoding_format": "float",
        }
        try:
            with self._send(payload) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except (error.HTTPError, error.URLError, OSError):
            raise EmbeddingError("Embedding request failed") from None
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            raise EmbeddingError("Embedding response was invalid") from None

        return _parse_embeddings_response(
            response_payload, self.dimensions, len(texts)
        )


def _read_non_empty_environment_value(name: str, default: str) -> str:
    value = os.getenv(name, default)
    if not isinstance(value, str) or not value.strip():
        raise EmbeddingError(f"{name} must be a non-empty string")
    return value.strip()


def _read_dimensions() -> int:
    raw_dimensions = os.getenv("CLAIMGUARD_EMBEDDING_DIMENSIONS")
    if raw_dimensions is None:
        return DEFAULT_DIMENSIONS
    try:
        dimensions = int(raw_dimensions)
    except (TypeError, ValueError):
        raise EmbeddingError("CLAIMGUARD_EMBEDDING_DIMENSIONS must be a positive integer") from None
    if dimensions <= 0:
        raise EmbeddingError("CLAIMGUARD_EMBEDDING_DIMENSIONS must be a positive integer")
    return dimensions


def _build_sender(
    api_key: str, base_url: str, transport: Transport
) -> Callable[[dict[str, object]], Any]:
    endpoint = f"{base_url}/embeddings"

    def send(payload: dict[str, object]) -> Any:
        body = json.dumps(payload).encode("utf-8")
        embedding_request = request.Request(
            endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        return transport(embedding_request, timeout=REQUEST_TIMEOUT_SECONDS)

    return send


def _validate_texts(texts: object) -> None:
    if not isinstance(texts, list) or not texts:
        raise EmbeddingError("Embedding input must be a non-empty list of strings")
    if any(not isinstance(text, str) or not text.strip() for text in texts):
        raise EmbeddingError("Embedding input must contain only non-empty strings")


def _parse_embeddings_response(
    payload: object, dimensions: int, expected_count: int
) -> list[list[float]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise EmbeddingError("Embedding response was invalid")

    indexed_embeddings: list[tuple[int, list[float]]] = []
    for item in payload["data"]:
        if not isinstance(item, dict):
            raise EmbeddingError("Embedding response was invalid")
        response_index = item.get("index")
        vector = item.get("embedding")
        if (
            isinstance(response_index, bool)
            or not isinstance(response_index, int)
            or not isinstance(vector, list)
            or len(vector) != dimensions
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                for value in vector
            )
        ):
            raise EmbeddingError("Embedding response was invalid")
        indexed_embeddings.append((response_index, list(vector)))

    indexed_embeddings.sort(key=lambda item: item[0])
    if [index for index, _ in indexed_embeddings] != list(range(expected_count)):
        raise EmbeddingError("Embedding response was invalid")
    return [vector for _, vector in indexed_embeddings]
