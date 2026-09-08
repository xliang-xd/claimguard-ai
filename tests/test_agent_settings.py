import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.agent_runtime.settings import (
    AgentSettingsError,
    load_agent_runtime_settings,
)


class AgentRuntimeSettingsTest(unittest.TestCase):
    def test_loads_qwen_defaults_and_disables_openai_tracing(self):
        settings = load_agent_runtime_settings(
            {
                "DASHSCOPE_API_KEY": "test-key",
                "CLAIMGUARD_DASHSCOPE_BASE_URL": (
                    "https://workspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
                ),
            }
        )

        self.assertEqual(settings.api_key, "test-key")
        self.assertEqual(
            settings.base_url,
            "https://workspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        )
        self.assertEqual(settings.router_model, "qwen3.8-flash")
        self.assertEqual(settings.policy_model, "qwen3.7-plus")
        self.assertFalse(settings.openai_tracing_enabled)

    def test_loads_explicit_models_and_enables_openai_tracing(self):
        settings = load_agent_runtime_settings(
            {
                "DASHSCOPE_API_KEY": "test-key",
                "CLAIMGUARD_ROUTER_MODEL": "router-model",
                "CLAIMGUARD_POLICY_MODEL": "policy-model",
                "CLAIMGUARD_OPENAI_TRACING_ENABLED": "true",
            }
        )

        self.assertEqual(settings.router_model, "router-model")
        self.assertEqual(settings.policy_model, "policy-model")
        self.assertTrue(settings.openai_tracing_enabled)

    def test_loads_project_dotenv_when_environment_is_not_provided(self):
        with TemporaryDirectory() as directory:
            project_path = Path(directory)
            (project_path / ".env").write_text(
                "DASHSCOPE_API_KEY=local-test-key\n"
                "CLAIMGUARD_ROUTER_MODEL=dotenv-router-model\n"
                "CLAIMGUARD_POLICY_MODEL=dotenv-policy-model\n"
                "CLAIMGUARD_OPENAI_TRACING_ENABLED=true\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                with patch("claimguard.config.Path.cwd", return_value=project_path):
                    settings = load_agent_runtime_settings()

        self.assertEqual(settings.api_key, "local-test-key")
        self.assertEqual(settings.router_model, "dotenv-router-model")
        self.assertEqual(settings.policy_model, "dotenv-policy-model")
        self.assertTrue(settings.openai_tracing_enabled)

    def test_requires_api_key_without_disclosing_configuration(self):
        with self.assertRaises(AgentSettingsError) as context:
            load_agent_runtime_settings({})

        self.assertEqual(str(context.exception), "DASHSCOPE_API_KEY is required")

    def test_repr_does_not_disclose_api_key(self):
        api_key = "sensitive-test-key"
        settings = load_agent_runtime_settings({"DASHSCOPE_API_KEY": api_key})

        self.assertNotIn(api_key, repr(settings))

    def test_rejects_empty_model_value_by_configuration_name(self):
        with self.assertRaises(AgentSettingsError) as context:
            load_agent_runtime_settings(
                {
                    "DASHSCOPE_API_KEY": "sensitive-test-key",
                    "CLAIMGUARD_ROUTER_MODEL": "   ",
                }
            )

        self.assertEqual(
            str(context.exception),
            "CLAIMGUARD_ROUTER_MODEL must be a non-empty string",
        )
        self.assertNotIn("sensitive-test-key", str(context.exception))

    def test_rejects_non_boolean_tracing_value_without_disclosing_values(self):
        with self.assertRaises(AgentSettingsError) as context:
            load_agent_runtime_settings(
                {
                    "DASHSCOPE_API_KEY": "sensitive-test-key",
                    "CLAIMGUARD_OPENAI_TRACING_ENABLED": "sensitive-invalid-value",
                }
            )

        self.assertEqual(
            str(context.exception),
            "CLAIMGUARD_OPENAI_TRACING_ENABLED must be true or false",
        )
        self.assertNotIn("sensitive-test-key", str(context.exception))
        self.assertNotIn("sensitive-invalid-value", str(context.exception))


if __name__ == "__main__":
    unittest.main()
