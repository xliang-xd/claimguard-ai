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


if __name__ == "__main__":
    unittest.main()
