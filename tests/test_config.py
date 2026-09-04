import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.config import load_local_environment
from claimguard.embeddings import DashScopeEmbeddingClient


class LocalEnvironmentTest(unittest.TestCase):
    def test_loads_known_values_from_dotenv_when_environment_is_absent(self):
        with TemporaryDirectory() as directory:
            dotenv_path = Path(directory) / ".env"
            dotenv_path.write_text(
                "DASHSCOPE_API_KEY=local-test-key\n"
                "CLAIMGUARD_EMBEDDING_MODEL=local-embedding-model\n"
                "UNRELATED_VALUE=must-not-load\n",
                encoding="utf-8",
            )
            environment = {}

            load_local_environment(dotenv_path, environment)

        self.assertEqual(environment["DASHSCOPE_API_KEY"], "local-test-key")
        self.assertEqual(
            environment["CLAIMGUARD_EMBEDDING_MODEL"], "local-embedding-model"
        )
        self.assertNotIn("UNRELATED_VALUE", environment)

    def test_environment_values_override_dotenv_values(self):
        with TemporaryDirectory() as directory:
            dotenv_path = Path(directory) / ".env"
            dotenv_path.write_text(
                "DASHSCOPE_API_KEY=dotenv-key\n"
                "CLAIMGUARD_EMBEDDING_MODEL=dotenv-model\n",
                encoding="utf-8",
            )
            environment = {
                "DASHSCOPE_API_KEY": "process-key",
                "CLAIMGUARD_EMBEDDING_MODEL": "process-model",
            }

            load_local_environment(dotenv_path, environment)

        self.assertEqual(environment["DASHSCOPE_API_KEY"], "process-key")
        self.assertEqual(environment["CLAIMGUARD_EMBEDDING_MODEL"], "process-model")

    def test_embedding_client_uses_project_dotenv_without_logging_secret(self):
        with TemporaryDirectory() as directory:
            project_path = Path(directory)
            (project_path / ".env").write_text(
                "DASHSCOPE_API_KEY=local-test-key\n"
                "CLAIMGUARD_EMBEDDING_MODEL=dotenv-model\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                with patch("claimguard.config.Path.cwd", return_value=project_path):
                    client = DashScopeEmbeddingClient(transport=lambda *_: None)

        self.assertEqual(client.model, "dotenv-model")


if __name__ == "__main__":
    unittest.main()
