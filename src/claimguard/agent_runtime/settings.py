from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os

from claimguard.config import load_project_environment


DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_ROUTER_MODEL = "qwen3.8-flash"
DEFAULT_POLICY_MODEL = "qwen3.7-plus"


class AgentSettingsError(ValueError):
    """Raised when Agent runtime configuration is invalid."""


@dataclass(frozen=True)
class AgentRuntimeSettings:
    api_key: str
    base_url: str
    router_model: str
    policy_model: str
    openai_tracing_enabled: bool


def load_agent_runtime_settings(
    environment: Mapping[str, str] | None = None,
) -> AgentRuntimeSettings:
    if environment is None:
        load_project_environment()
        source: Mapping[str, str] = os.environ
    else:
        source = environment

    return AgentRuntimeSettings(
        api_key=_required(source, "DASHSCOPE_API_KEY"),
        base_url=_value(source, "CLAIMGUARD_DASHSCOPE_BASE_URL", DEFAULT_BASE_URL),
        router_model=_value(source, "CLAIMGUARD_ROUTER_MODEL", DEFAULT_ROUTER_MODEL),
        policy_model=_value(source, "CLAIMGUARD_POLICY_MODEL", DEFAULT_POLICY_MODEL),
        openai_tracing_enabled=_boolean(
            source, "CLAIMGUARD_OPENAI_TRACING_ENABLED", False
        ),
    )


def _required(source: Mapping[str, str], name: str) -> str:
    value = source.get(name)
    if not isinstance(value, str) or not value.strip():
        raise AgentSettingsError(f"{name} is required")
    return value.strip()


def _value(source: Mapping[str, str], name: str, default: str) -> str:
    value = source.get(name, default)
    if not isinstance(value, str) or not value.strip():
        raise AgentSettingsError(f"{name} must be a non-empty string")
    return value.strip()


def _boolean(source: Mapping[str, str], name: str, default: bool) -> bool:
    value = source.get(name)
    if value is None:
        return default
    if isinstance(value, str):
        normalized_value = value.strip().lower()
        if normalized_value == "true":
            return True
        if normalized_value == "false":
            return False
    raise AgentSettingsError(f"{name} must be true or false")
