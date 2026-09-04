from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.cli import main
from claimguard.embeddings import EmbeddingError
from claimguard.semantic_judge import SemanticJudgeError, SemanticJudgment


class StaticEmbeddingClient:
    model = "offline-static"

    def __init__(self):
        self.vectors = {
            "对符合赔付条件的住院治疗，保险人在计算可赔付金额前，会先扣除保单约定的免赔额。": [
                1.0,
                0.0,
            ],
            "等待期内开始的疾病治疗不予赔付，除非保单特别约定了例外情形。": [
                0.0,
                1.0,
            ],
            "只有列入疾病保障清单的疾病，才可以申请疾病医疗赔付。": [
                0.0,
                1.0,
            ],
            "意外事故是指突发、外来、非故意且直接导致被保险宠物身体受伤的事件。": [
                0.0,
                1.0,
            ],
            "我的宠物住院花了1800元，为什么理赔只赔800元？ Claim amount dispute: deductible": [
                1.0,
                0.0,
            ],
        }

    def embed(self, texts):
        return [self.vectors[text] for text in texts]


class KeyRequiredEmbeddingClient:
    def __init__(self):
        raise EmbeddingError("DASHSCOPE_API_KEY is required for embeddings")


class StaticJudge:
    def judge(self, conversation):
        return [
            SemanticJudgment(
                rule_id="SEM-005",
                violated=True,
                evidence="您的理赔明天一定到账。",
                reasoning="客服作出了无依据的到账承诺。",
                recommendation="说明处理时效需要以审核结果为准。",
                confidence="high",
            )
        ]


class KeyRequiredJudge:
    def __init__(self):
        raise SemanticJudgeError("offline-test-credential is required")


class CLITest(unittest.TestCase):
    def run_main(self, argv):
        try:
            return main(argv)
        except SystemExit as error:
            return error.code
        except (KeyError, TypeError):
            return 1

    def test_cli_creates_a_valid_knowledge_index(self):
        repository_root = Path(__file__).resolve().parents[1]
        policy_path = repository_root / "data/knowledge/petcare-plus-policy-zh.md"

        with tempfile.TemporaryDirectory() as directory:
            index_path = Path(directory) / ".claimguard" / "petcare-plus-policy.json"
            stdout = io.StringIO()
            with patch(
                "claimguard.cli.DashScopeEmbeddingClient",
                StaticEmbeddingClient,
                create=True,
            ):
                with redirect_stdout(stdout):
                    exit_code = self.run_main(
                        ["index", str(policy_path), "--output", str(index_path)]
                    )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.getvalue(), "")
            payload = json.loads(index_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["embedding_model"], "offline-static")
            self.assertEqual(payload["dimensions"], 2)
            self.assertEqual(payload["clauses"][0]["id"], "12")

    def test_cli_uses_index_without_embeddings_for_nonknowledge_findings(self):
        repository_root = Path(__file__).resolve().parents[1]
        policy_path = repository_root / "data/knowledge/petcare-plus-policy-zh.md"

        with tempfile.TemporaryDirectory() as directory:
            fixture_path = Path(directory) / "semantic-only.json"
            fixture_path.write_text(
                json.dumps(
                    {
                        "id": "semantic-only",
                        "scenario": "A semantic-only QA case.",
                        "messages": [
                            {"role": "customer", "content": "Hello."},
                            {
                                "role": "agent",
                                "content": "That is the final result.",
                            },
                        ],
                        "expected_risks": [],
                    }
                ),
                encoding="utf-8",
            )
            index_path = Path(directory) / "petcare-plus-policy.json"
            with patch(
                "claimguard.cli.DashScopeEmbeddingClient",
                StaticEmbeddingClient,
                create=True,
            ):
                self.assertEqual(
                    self.run_main(
                        ["index", str(policy_path), "--output", str(index_path)]
                    ),
                    0,
                )

            stdout = io.StringIO()
            with patch(
                "claimguard.cli.DashScopeEmbeddingClient",
                KeyRequiredEmbeddingClient,
            ):
                with redirect_stdout(stdout):
                    exit_code = self.run_main(
                        [str(fixture_path), "--index", str(index_path)]
                    )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["findings"][0]["rule_id"], "SEM-003")
            self.assertIsNone(payload["findings"][0]["grounding"])

    def test_cli_emits_grounded_qa_report_from_knowledge_index(self):
        repository_root = Path(__file__).resolve().parents[1]
        policy_path = repository_root / "data/knowledge/petcare-plus-policy-zh.md"
        conversation_path = repository_root / "examples/conversations/zh-deductible-dispute.json"

        with tempfile.TemporaryDirectory() as directory:
            index_path = Path(directory) / "petcare-plus-policy.json"
            with patch(
                "claimguard.cli.DashScopeEmbeddingClient",
                StaticEmbeddingClient,
                create=True,
            ):
                self.assertEqual(
                    self.run_main(
                        ["index", str(policy_path), "--output", str(index_path)]
                    ),
                    0,
                )
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    exit_code = self.run_main(
                        [str(conversation_path), "--index", str(index_path)]
                    )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["findings"][0]["grounding"]["clause_id"], "12")

    def test_cli_reports_a_missing_knowledge_index(self):
        repository_root = Path(__file__).resolve().parents[1]
        conversation_path = repository_root / "examples/conversations/zh-deductible-dispute.json"
        missing_index_path = repository_root / "missing-index.json"
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            exit_code = self.run_main(
                [str(conversation_path), "--index", str(missing_index_path)]
            )

        self.assertEqual(exit_code, 2)
        self.assertEqual(
            stderr.getvalue(), f"Unable to load knowledge index {missing_index_path}\n"
        )

    def test_cli_reports_invalid_conversation_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture_path = Path(directory) / "invalid-conversation.json"
            fixture_path.write_text('{"id": "missing-fields"}', encoding="utf-8")
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                exit_code = self.run_main([str(fixture_path)])

        self.assertEqual(exit_code, 2)
        self.assertEqual(stderr.getvalue(), "Invalid conversation fixture\n")

    def test_cli_creates_no_semantic_client_without_llm(self):
        fixture_path = Path("examples/conversations/zh-semantic-qa.json")
        stdout = io.StringIO()

        with patch("claimguard.cli.DashScopeSemanticJudgeClient", KeyRequiredJudge):
            with redirect_stdout(stdout):
                exit_code = self.run_main([str(fixture_path)])

        self.assertEqual(exit_code, 0)

    def test_cli_adds_semantic_output_with_llm(self):
        fixture_path = Path("examples/conversations/zh-semantic-qa.json")
        stdout = io.StringIO()

        with patch("claimguard.cli.DashScopeSemanticJudgeClient", StaticJudge):
            with redirect_stdout(stdout):
                exit_code = self.run_main([str(fixture_path), "--llm"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["findings"][0]["rule_id"], "SEM-005")
        self.assertEqual(payload["findings"][0]["judge"], "semantic_llm")

    def test_cli_returns_two_for_semantic_judge_error(self):
        fixture_path = Path("examples/conversations/zh-semantic-qa.json")
        stderr = io.StringIO()

        with patch("claimguard.cli.DashScopeSemanticJudgeClient", KeyRequiredJudge):
            with redirect_stderr(stderr):
                exit_code = self.run_main([str(fixture_path), "--llm"])

        self.assertEqual(exit_code, 2)
        self.assertNotIn("offline-test-credential", stderr.getvalue())

    def test_cli_rejects_llm_for_index_command(self):
        repository_root = Path(__file__).resolve().parents[1]
        policy_path = repository_root / "data/knowledge/petcare-plus-policy-zh.md"
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            exit_code = self.run_main(["index", str(policy_path), "--llm"])

        self.assertEqual(exit_code, 2)
        self.assertIn("--llm is only supported with conversation QA", stderr.getvalue())

    def test_cli_outputs_qa_report_json_for_conversation_fixture(self):
        command = [
            sys.executable,
            "-m",
            "claimguard.cli",
            "examples/conversations/claim-amount-dispute.json",
        ]
        result = subprocess.run(
            command,
            check=False,
            cwd=Path(__file__).resolve().parents[1],
            env={"PYTHONPATH": "src"},
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["conversation_id"], "claim-amount-dispute-001")
        self.assertEqual(payload["score"], 70)
        self.assertEqual(payload["findings"][0]["rule_id"], "SEM-002")


if __name__ == "__main__":
    unittest.main()
