from __future__ import annotations

import os
from pathlib import Path
from typing import MutableMapping


LOCAL_CONFIGURATION_NAMES = frozenset(
    {
        "DASHSCOPE_API_KEY",
        "CLAIMGUARD_DASHSCOPE_BASE_URL",
        "CLAIMGUARD_EMBEDDING_MODEL",
        "CLAIMGUARD_EMBEDDING_DIMENSIONS",
    }
)


def load_project_environment() -> None:
    """Load recognized local configuration values from the current project."""
    load_local_environment(Path.cwd() / ".env", os.environ)


def load_local_environment(path: Path, environment: MutableMapping[str, str]) -> None:
    """Add recognized values from a local .env file without overriding the process."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return

    for line in lines:
        name, separator, raw_value = line.strip().partition("=")
        if not separator or not name or name.startswith("#"):
            continue
        if name not in LOCAL_CONFIGURATION_NAMES or name in environment:
            continue
        environment[name] = _parse_value(raw_value)


def _parse_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
