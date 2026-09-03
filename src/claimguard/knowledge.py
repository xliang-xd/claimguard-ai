from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re


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
    clauses: list[IndexedClause]


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
        "schema_version": SCHEMA_VERSION,
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
    if not isinstance(payload.get("clauses"), list):
        raise KnowledgeError("Knowledge index clauses must be a list")

    clauses = [_parse_indexed_clause(item) for item in payload["clauses"]]
    index = KnowledgeIndex(clauses=clauses)
    _validate_index(index)
    return index


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
    if not index.clauses:
        raise KnowledgeError("Knowledge index must contain at least one clause")

    _ensure_unique_clause_ids([indexed_clause.clause for indexed_clause in index.clauses])
    vector_length: int | None = None
    for indexed_clause in index.clauses:
        if not isinstance(indexed_clause, IndexedClause):
            raise KnowledgeError("Knowledge index entries must be IndexedClause values")
        _validate_policy_clause(indexed_clause.clause)
        _validate_vector(indexed_clause.vector)
        if vector_length is None:
            vector_length = len(indexed_clause.vector)
        elif len(indexed_clause.vector) != vector_length:
            raise KnowledgeError("Knowledge index vectors must have matching lengths")


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
