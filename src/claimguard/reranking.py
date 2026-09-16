from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
from typing import Any, Callable, Optional, Protocol
from urllib import error, request

from claimguard.config import load_project_environment
from claimguard.knowledge import PolicyClause, RetrievedClause


DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3-rerank"
REQUEST_TIMEOUT_SECONDS = 30


class RerankingError(ValueError):
    pass


@dataclass(frozen=True)
class RerankedClause:
    clause: PolicyClause
    retrieval_score: float
    rerank_score: float


class Reranker(Protocol):
    model: str

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        ...


Transport = Callable[[request.Request, int], Any]


class QwenReranker:
    def __init__(self, transport: Optional[Transport] = None):
        load_project_environment()
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise RerankingError("DASHSCOPE_API_KEY 是重排所必需的")

        base_url = _read_non_empty_environment_value(
            "CLAIMGUARD_DASHSCOPE_BASE_URL", DEFAULT_BASE_URL
        )
        self.model = _read_non_empty_environment_value(
            "CLAIMGUARD_RERANK_MODEL", DEFAULT_MODEL
        )
        self._send = _build_sender(
            api_key,
            base_url.rstrip("/"),
            transport or request.urlopen,
        )

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        _validate_query(query)
        _validate_documents(documents)
        payload = {
            "model": self.model,
            "query": query,
            "documents": documents,
        }
        try:
            with self._send(payload) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except (error.HTTPError, error.URLError, OSError):
            raise RerankingError("Reranking request failed") from None
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            raise RerankingError("Reranking response was invalid") from None

        return _parse_reranking_response(response_payload, len(documents))


def rerank_clauses(
    query: str, candidates: list[RetrievedClause], reranker: Reranker
) -> list[RerankedClause]:
    _validate_query(query)
    _validate_candidates(candidates)
    if not candidates:
        return []

    documents = [candidate.clause.content for candidate in candidates]
    try:
        scores = reranker.rerank(query, documents)
    except Exception:
        raise RerankingError("重排请求失败") from None

    _validate_rerank_scores(scores, len(candidates))
    reranked = [
        RerankedClause(
            clause=candidate.clause,
            retrieval_score=candidate.score,
            rerank_score=score,
        )
        for candidate, score in zip(candidates, scores)
    ]
    return sorted(
        reranked,
        key=lambda item: (-item.rerank_score, -item.retrieval_score, item.clause.id),
    )


def _validate_query(query: object) -> None:
    if not isinstance(query, str) or not query.strip():
        raise RerankingError("重排查询必须为非空字符串")


def _validate_candidates(candidates: object) -> None:
    if not isinstance(candidates, list):
        raise RerankingError("重排候选必须为列表")

    clause_ids: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, RetrievedClause):
            raise RerankingError("重排候选必须为已召回条款")
        if not _is_finite_number(candidate.score):
            raise RerankingError("召回分数必须为有限数值")
        clause_ids.append(candidate.clause.id)
    if len(clause_ids) != len(set(clause_ids)):
        raise RerankingError("重排候选的条款 ID 必须唯一")


def _validate_rerank_scores(scores: object, expected_count: int) -> None:
    if not isinstance(scores, list) or len(scores) != expected_count:
        raise RerankingError("重排分数数量必须与候选数量一致")
    if any(not _is_finite_number(score) for score in scores):
        raise RerankingError("重排分数必须为有限数值")


def _is_finite_number(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _read_non_empty_environment_value(name: str, default: str) -> str:
    value = os.getenv(name, default)
    if not isinstance(value, str) or not value.strip():
        raise RerankingError(f"{name} 必须为非空字符串")
    return value.strip()


def _build_sender(
    api_key: str, base_url: str, transport: Transport
) -> Callable[[dict[str, object]], Any]:
    endpoint = f"{base_url}/reranks"

    def send(payload: dict[str, object]) -> Any:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        reranking_request = request.Request(
            endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        return transport(reranking_request, timeout=REQUEST_TIMEOUT_SECONDS)

    return send


def _validate_documents(documents: object) -> None:
    if not isinstance(documents, list) or not documents:
        raise RerankingError("重排条款必须为非空字符串列表")
    if any(not isinstance(document, str) or not document.strip() for document in documents):
        raise RerankingError("重排条款必须为非空字符串列表")


def _parse_reranking_response(payload: object, expected_count: int) -> list[float]:
    try:
        results = payload["output"]["results"]
    except (KeyError, TypeError):
        raise RerankingError("Reranking response was invalid") from None
    if not isinstance(results, list):
        raise RerankingError("Reranking response was invalid")

    indexed_scores: list[tuple[int, float]] = []
    for result in results:
        if not isinstance(result, dict):
            raise RerankingError("Reranking response was invalid")
        index = result.get("index")
        score = result.get("relevance_score")
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or not _is_finite_number(score)
        ):
            raise RerankingError("Reranking response was invalid")
        indexed_scores.append((index, float(score)))

    indexed_scores.sort(key=lambda item: item[0])
    if [index for index, _ in indexed_scores] != list(range(expected_count)):
        raise RerankingError("Reranking response was invalid")
    return [score for _, score in indexed_scores]
