from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.conversation import load_conversation
from claimguard.rule_runner import run_rules


class RuleRunnerTest(unittest.TestCase):
    def test_matches_demo_risks_from_conversation_text(self):
        conversation = load_conversation(
            Path("examples/conversations/claim-amount-dispute.json")
        )

        matches = run_rules(conversation)

        self.assertEqual(
            [match.rule_id for match in matches], ["SEM-002", "SEM-003", "RAG-001"]
        )
        self.assertIn("final result", matches[0].evidence.lower())
        self.assertIn("only reimburse", matches[2].evidence.lower())

    def test_matches_each_chinese_knowledge_case_without_cross_routing(self):
        fixtures = {
            "zh-deductible-dispute.json": "RAG-001",
            "zh-waiting-period-denial.json": "RAG-002",
            "zh-coverage-denial.json": "RAG-003",
            "zh-accident-definition.json": "RAG-004",
            "zh-denial-citation.json": "RAG-005",
        }

        for fixture_name, rule_id in fixtures.items():
            with self.subTest(fixture_name=fixture_name):
                conversation = load_conversation(
                    Path("examples/conversations") / fixture_name
                )

                self.assertEqual(
                    [match.rule_id for match in run_rules(conversation)], [rule_id]
                )


if __name__ == "__main__":
    unittest.main()
