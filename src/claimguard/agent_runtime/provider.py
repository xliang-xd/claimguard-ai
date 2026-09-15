from __future__ import annotations

from agents import RunConfig
from agents.models.interface import Model, ModelProvider
from agents.models.openai_responses import OpenAIResponsesModel
from openai import AsyncOpenAI

from claimguard.agent_runtime.settings import AgentRuntimeSettings


class AgentProviderError(ValueError):
    """Raised when Agent model provider configuration is invalid."""


class QwenModelProvider(ModelProvider):
    def __init__(self, settings: AgentRuntimeSettings):
        self._client = AsyncOpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url.rstrip("/"),
        )

    def get_model(self, model_name: str | None) -> Model:
        if not model_name or not model_name.strip():
            raise AgentProviderError("Agent model name must be non-empty")
        return OpenAIResponsesModel(
            model=model_name.strip(),
            openai_client=self._client,
        )


def build_run_config(
    provider: ModelProvider,
    tracing_enabled: bool,
) -> RunConfig:
    return RunConfig(
        model_provider=provider,
        tracing_disabled=not tracing_enabled,
    )
