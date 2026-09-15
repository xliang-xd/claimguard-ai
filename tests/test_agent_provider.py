from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.agent_runtime.provider import (
    AgentProviderError,
    QwenModelProvider,
    build_run_config,
)
from claimguard.agent_runtime.settings import AgentRuntimeSettings


class FakeProvider:
    def get_model(self, model_name):
        raise AssertionError("get_model must not be called while building RunConfig")


class QwenModelProviderTest(unittest.TestCase):
    @patch("claimguard.agent_runtime.provider.AsyncOpenAI")
    def test_builds_responses_model_with_qwen_client(self, client_type):
        settings = AgentRuntimeSettings(
            api_key="test-key",
            base_url=(
                "https://workspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
            ),
            router_model="qwen3.8-flash",
            policy_model="qwen3.7-plus",
            openai_tracing_enabled=False,
        )
        provider = QwenModelProvider(settings)

        model = provider.get_model("qwen3.8-flash")

        client_type.assert_called_once_with(
            api_key="test-key",
            base_url=settings.base_url,
        )
        self.assertEqual(model.model, "qwen3.8-flash")

    def test_run_config_disables_openai_tracing_by_default(self):
        run_config = build_run_config(FakeProvider(), tracing_enabled=False)

        self.assertTrue(run_config.tracing_disabled)

    def test_run_config_allows_explicit_openai_tracing(self):
        run_config = build_run_config(FakeProvider(), tracing_enabled=True)

        self.assertFalse(run_config.tracing_disabled)

    @patch("claimguard.agent_runtime.provider.AsyncOpenAI")
    def test_removes_trailing_slash_from_qwen_base_url(self, client_type):
        settings = AgentRuntimeSettings(
            api_key="test-key",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1/",
            router_model="qwen3.8-flash",
            policy_model="qwen3.7-plus",
            openai_tracing_enabled=False,
        )

        QwenModelProvider(settings)

        client_type.assert_called_once_with(
            api_key="test-key",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

    @patch("claimguard.agent_runtime.provider.AsyncOpenAI")
    def test_rejects_blank_model_name_without_disclosing_credentials(
        self, client_type
    ):
        api_key = "sensitive-test-key"
        provider = QwenModelProvider(
            AgentRuntimeSettings(
                api_key=api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                router_model="qwen3.8-flash",
                policy_model="qwen3.7-plus",
                openai_tracing_enabled=False,
            )
        )

        with self.assertRaises(AgentProviderError) as context:
            provider.get_model("   ")

        self.assertEqual(str(context.exception), "Agent model name must be non-empty")
        self.assertNotIn(api_key, str(context.exception))
        self.assertNotIn(api_key, repr(context.exception))

    @patch("claimguard.agent_runtime.provider.AsyncOpenAI")
    def test_provider_repr_does_not_disclose_api_key(self, client_type):
        api_key = "sensitive-test-key"
        provider = QwenModelProvider(
            AgentRuntimeSettings(
                api_key=api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                router_model="qwen3.8-flash",
                policy_model="qwen3.7-plus",
                openai_tracing_enabled=False,
            )
        )

        self.assertNotIn(api_key, repr(provider))


if __name__ == "__main__":
    unittest.main()
