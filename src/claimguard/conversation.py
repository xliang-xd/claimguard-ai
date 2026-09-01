from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class Message:
    role: str
    content: str


@dataclass(frozen=True)
class Conversation:
    id: str
    scenario: str
    messages: list[Message]
    expected_risks: list[str]


def load_conversation(path: str | Path) -> Conversation:
    with Path(path).open(encoding="utf-8") as file:
        payload = json.load(file)

    return Conversation(
        id=payload["id"],
        scenario=payload["scenario"],
        messages=[Message(**message) for message in payload["messages"]],
        expected_risks=list(payload.get("expected_risks", [])),
    )
