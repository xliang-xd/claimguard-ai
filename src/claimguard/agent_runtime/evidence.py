from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceRecord:
    clause_id: str
    title: str
    content: str
    source_path: str
    retrieval_score: float
    rerank_score: float


class EvidenceLedger:
    """保存当前进程内、供后续引用核验使用的已选证据。"""

    def __init__(self) -> None:
        self._records: list[EvidenceRecord] = []

    def record(self, records: list[EvidenceRecord]) -> None:
        self._records.extend(records)

    def snapshot(self) -> tuple[EvidenceRecord, ...]:
        return tuple(self._records)

    def clear(self) -> None:
        self._records.clear()
