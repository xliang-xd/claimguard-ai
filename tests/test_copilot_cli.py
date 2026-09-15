from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.agent_runtime.runtime import CopilotTurnResult
from claimguard.agent_runtime.settings import AgentSettingsError
from claimguard.copilot_cli import main


class CopilotCLITest(unittest.TestCase):
    def test_emits_structured_draft_result(self):
        observed_audits: list[str] = []

        async def execute_turn(args):
            observed_audits.append(args.audit)
            return CopilotTurnResult(
                status="draft_ready",
                session_id="demo-session",
                current_agent="Policy Agent",
                draft="客服草稿：根据等待期条款，这是客服回复草稿。",
                audit_id="audit-000001",
            )

        with TemporaryDirectory() as directory:
            index_path = Path(directory) / "policy.json"
            index_path.write_text("{}", encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                code = main(
                    [
                        "--tenant-id", "demo-tenant",
                        "--user-id", "agent-7",
                        "--session-id", "demo-session",
                        "--index", str(index_path),
                        "等待期是什么？",
                    ],
                    turn_executor=execute_turn,
                )

        self.assertEqual(code, 0)
        self.assertEqual(
            json.loads(output.getvalue()),
            {
                "status": "draft_ready",
                "session_id": "demo-session",
                "current_agent": "Policy Agent",
                "draft": "客服草稿：根据等待期条款，这是客服回复草稿。",
                "audit_id": "audit-000001",
            },
        )
        self.assertEqual(observed_audits, [".claimguard/audit.jsonl"])
        self.assertNotIn("test-key", output.getvalue())

    def test_missing_index_returns_operator_error_before_executor_runs(self):
        async def execute_turn(_args):
            raise AssertionError("executor must not run for a missing index")

        stderr = StringIO()
        with redirect_stderr(stderr):
            code = main(
                [
                    "--tenant-id", "demo-tenant",
                    "--user-id", "agent-7",
                    "--session-id", "demo-session",
                    "--index", "missing.json",
                    "等待期是什么？",
                ],
                turn_executor=execute_turn,
            )

        self.assertEqual(code, 2)
        self.assertEqual(stderr.getvalue(), "Knowledge index not found\n")

    def test_module_entrypoint_reports_missing_index_to_operator(self):
        repository_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "claimguard.copilot_cli",
                "--tenant-id",
                "demo-tenant",
                "--user-id",
                "agent-7",
                "--session-id",
                "demo-session",
                "--index",
                "missing.json",
                "等待期是什么？",
            ],
            check=False,
            cwd=repository_root,
            env={"PYTHONPATH": "src"},
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "Knowledge index not found\n")

    def test_setup_error_is_generic_and_does_not_disclose_sensitive_details(self):
        async def execute_turn(_args):
            raise AgentSettingsError(
                "https://example.invalid/path?api_key=test-key Authorization: Bearer secret"
            )

        with TemporaryDirectory() as directory:
            index_path = Path(directory) / "policy.json"
            index_path.write_text("{}", encoding="utf-8")
            stderr = StringIO()
            with redirect_stderr(stderr):
                code = main(
                    [
                        "--tenant-id", "demo-tenant",
                        "--user-id", "agent-7",
                        "--session-id", "demo-session",
                        "--index", str(index_path),
                        "等待期是什么？",
                    ],
                    turn_executor=execute_turn,
                )

        self.assertEqual(code, 2)
        self.assertEqual(stderr.getvalue(), "Copilot request failed\n")


if __name__ == "__main__":
    unittest.main()
