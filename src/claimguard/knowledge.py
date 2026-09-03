from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re

from .embeddings import EmbeddingClient


CLAUSE_HEADING = re.compile(
    r"^## 条款\s*(?P<id>\d+)\s*[：:]\s*(?P<title>.+?)\s*$"
)
SCHEMA_VERSION = 1


class KnowledgeError(ValueError):
    """Raised when policy clauses or a persisted knowledge index are invalid."""


@dataclass(frozen=True)
class PolicyClause:
    id: str
    title: str
    content: str
    source_path: str


@dataclass(frozen=True)
class IndexedClause:
    clause: PolicyClause
    vector: list[float]


@dataclass(frozen=True)
class KnowledgeIndex:
    schema_version: int
    embedding_model: str
    dimensions: int
    clauses: list[IndexedClause]


@dataclass(frozen=True)
class RetrievedClause:
    clause: PolicyClause
    score: float


def parse_policy_markdown(path: str | Path) -> list[PolicyClause]:
    source_path = Path(path)
    clauses: list[PolicyClause] = []
    current_id: str | None = None
    current_title: str | None = None
    current_content: list[str] = []

    for line in source_path.read_text(encoding="utf-8").splitlines():
        match = CLAUSE_HEADING.match(line)
        if match:
            if current_id is not None:
                clauses.append(
                    _build_clause(
                        current_id, current_title, current_content, source_path
                    )
                )
            current_id = match.group("id")
            current_title = match.group("title")
            current_content = []
        elif current_id is not None:
            current_content.append(line)

    if current_id is not None:
        clauses.append(
            _build_clause(current_id, current_title, current_content, source_path)
        )

    if not clauses:
        raise KnowledgeError(f"No clause headings found in {source_path}")

    _ensure_unique_clause_ids(clauses)
    return clauses


def save_knowledge_index(index: KnowledgeIndex, path: str | Path) -> None:
    _validate_index(index)
    payload = {
        "schema_version": index.schema_version,
        "embedding_model": index.embedding_model,
        "dimensions": index.dimensions,
        "clauses": [
            {
                "id": indexed_clause.clause.id,
                "title": indexed_clause.clause.title,
                "content": indexed_clause.clause.content,
                "source_path": indexed_clause.clause.source_path,
                "vector": indexed_clause.vector,
            }
            for indexed_clause in index.clauses
        ],
    }
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_knowledge_index(path: str | Path) -> KnowledgeIndex:
    source_path = Path(path)
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise KnowledgeError(f"Unable to load knowledge index {source_path}") from error

    if not isinstance(payload, dict):
        raise KnowledgeError("Knowledge index must be a JSON object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise KnowledgeError(f"Unsupported schema version: {payload.get('schema_version')!r}")
    required_fields = {"schema_version", "embedding_model", "dimensions", "clauses"}
    missing_fields = required_fields.difference(payload)
    if missing_fields:
        raise KnowledgeError(
            f"Knowledge index is missing fields: {', '.join(sorted(missing_fields))}"
        )
    if not isinstance(payload.get("clauses"), list):
        raise KnowledgeError("Knowledge index clauses must be a list")

    clauses = [_parse_indexed_clause(item) for item in payload["clauses"]]
    index = KnowledgeIndex(
        schema_version=payload["schema_version"],
        embedding_model=payload["embedding_model"],
        dimensions=payload["dimensions"],
        clauses=clauses,
    )
    _validate_index(index)
    return index


def build_knowledge_index(
    clauses: list[PolicyClause], client: EmbeddingClient
) -> KnowledgeIndex:
    if not isinstance(clauses, list) or not clauses:
        raise KnowledgeError("Knowledge index must contain at least one clause")
    for clause in clauses:
        _validate_policy_clause(clause)
    _ensure_unique_clause_ids(clauses)

    vectors = client.embed([clause.content for clause in clauses])
    if not isinstance(vectors, list) or len(vectors) != len(clauses):
        raise KnowledgeError("Embedding count must match the number of policy clauses")

    dimensions: int | None = None
    indexed_clauses: list[IndexedClause] = []
    for clause, vector in zip(clauses, vectors):
        _validate_vector(vector)
        if dimensions is None:
            dimensions = len(vector)
        elif len(vector) != dimensions:
            raise KnowledgeError("Knowledge index vectors must have matching lengths")
        indexed_clauses.append(IndexedClause(clause=clause, vector=list(vector)))

    index = KnowledgeIndex(
        schema_version=SCHEMA_VERSION,
        embedding_model=_embedding_model_name(client),
        dimensions=dimensions or 0,
        clauses=indexed_clauses,
    )
    _validate_index(index)
    return index


def retrieve_clauses(
    query: str, index: KnowledgeIndex, client: EmbeddingClient, top_k: int = 3
) -> list[RetrievedClause]:
    if not isinstance(query, str) or not query.strip():
        raise KnowledgeError("Retrieval query must be a non-empty string")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
        raise KnowledgeError("top_k must be a positive integer")

    _validate_index(index)
    query_vectors = client.embed([query])
    if not isinstance(query_vectors, list) or len(query_vectors) != 1:
        raise KnowledgeError("Query embedding must contain exactly one vector")
    query_vector = query_vectors[0]
    _validate_vector(query_vector)
    if len(query_vector) != index.dimensions:
        raise KnowledgeError("Query embedding dimensions do not match the knowledge index")

    retrieved = [
        RetrievedClause(
            clause=indexed_clause.clause,
            score=_cosine_similarity(query_vector, indexed_clause.vector),
        )
        for indexed_clause in index.clauses
    ]
    retrieved.sort(key=lambda item: (-item.score, item.clause.id))
    return retrieved[:top_k]


def _build_clause(
    clause_id: str,
    title: str | None,
    content_lines: list[str],
    source_path: Path,
) -> PolicyClause:
    content = "\n".join(content_lines).strip()
    if not title or not title.strip():
        raise KnowledgeError(f"Clause {clause_id} has no title")
    if not content:
        raise KnowledgeError(f"Clause {clause_id} has no content")
    return PolicyClause(
        id=clause_id,
        title=title.strip(),
        content=content,
        source_path=str(source_path),
    )


def _parse_indexed_clause(item: object) -> IndexedClause:
    if not isinstance(item, dict):
        raise KnowledgeError("Knowledge index clauses must be objects")

    required_fields = {"id", "title", "content", "source_path", "vector"}
    missing_fields = required_fields.difference(item)
    if missing_fields:
        raise KnowledgeError(
            f"Knowledge index clause is missing fields: {', '.join(sorted(missing_fields))}"
        )

    clause = PolicyClause(
        id=_require_non_empty_string(item["id"], "id"),
        title=_require_non_empty_string(item["title"], "title"),
        content=_require_non_empty_string(item["content"], "content"),
        source_path=_require_non_empty_string(item["source_path"], "source_path"),
    )
    vector = item["vector"]
    if not isinstance(vector, list):
        raise KnowledgeError("Knowledge index clause vector must be a list")
    return IndexedClause(clause=clause, vector=list(vector))


def _validate_index(index: KnowledgeIndex) -> None:
    if not isinstance(index, KnowledgeIndex):
        raise KnowledgeError("Knowledge index must be a KnowledgeIndex")
    if index.schema_version != SCHEMA_VERSION:
        raise KnowledgeError(f"Unsupported schema version: {index.schema_version!r}")
    _require_non_empty_string(index.embedding_model, "embedding model")
    _validate_dimensions(index.dimensions)
    if not isinstance(index.clauses, list) or not index.clauses:
        raise KnowledgeError("Knowledge index must contain at least one clause")

    clauses: list[PolicyClause] = []
    for indexed_clause in index.clauses:
        if not isinstance(indexed_clause, IndexedClause):
            raise KnowledgeError("Knowledge index entries must be IndexedClause values")
        _validate_policy_clause(indexed_clause.clause)
        _validate_vector(indexed_clause.vector)
        if len(indexed_clause.vector) != index.dimensions:
            raise KnowledgeError("Knowledge index vectors must have matching lengths")
        clauses.append(indexed_clause.clause)
    _ensure_unique_clause_ids(clauses)


def _ensure_unique_clause_ids(clauses: list[PolicyClause]) -> None:
    clause_ids = [clause.id for clause in clauses]
    if len(clause_ids) != len(set(clause_ids)):
        raise KnowledgeError("Policy clause IDs must be unique")


def _validate_policy_clause(clause: PolicyClause) -> None:
    if not isinstance(clause, PolicyClause):
        raise KnowledgeError("Knowledge index clause must be a PolicyClause")
    _require_non_empty_string(clause.id, "id")
    _require_non_empty_string(clause.title, "title")
    _require_non_empty_string(clause.content, "content")
    _require_non_empty_string(clause.source_path, "source_path")


def _require_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise KnowledgeError(f"Knowledge index clause {field_name} must be a non-empty string")
    return value


def _validate_vector(vector: object) -> None:
    if not isinstance(vector, list) or not vector:
        raise KnowledgeError("Knowledge index clause vector must be a non-empty list")
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        for value in vector
    ):
        raise KnowledgeError("Knowledge index vectors must contain only finite numbers")


def _validate_dimensions(dimensions: object) -> None:
    if isinstance(dimensions, bool) or not isinstance(dimensions, int) or dimensions <= 0:
        raise KnowledgeError("Knowledge index dimensions must be a positive integer")


def _embedding_model_name(client: EmbeddingClient) -> str:
    model = getattr(client, "model", "unknown")
    if not isinstance(model, str) or not model.strip():
        raise KnowledgeError("Embedding client model must be a non-empty string")
    return model.strip()


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    left_magnitude = math.sqrt(sum(value * value for value in left))
    right_magnitude = math.sqrt(sum(value * value for value in right))
    if left_magnitude == 0 or right_magnitude == 0:
        return 0.0
    return sum(left_value * right_value for left_value, right_value in zip(left, right)) / (
        left_magnitude * right_magnitude
    )
