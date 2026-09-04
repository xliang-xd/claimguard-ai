from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.conversation import load_conversation


class ConversationLoaderTest(unittest.TestCase):
    def test_loads_chinese_semantic_fixture_with_all_semantic_risks(self):
        conversation = load_conversation(
            Path("examples/conversations/zh-semantic-qa.json")
        )

        self.assertEqual(
            conversation.expected_risks,
            ["SEM-002", "SEM-003", "SEM-004", "SEM-005"],
        )

    def test_loads_conversation_fixture_messages_and_expected_risks(self):
        fixture = Path("examples/conversations/claim-amount-dispute.json")

        conversation = load_conversation(fixture)

        self.assertEqual(conversation.id, "claim-amount-dispute-001")
        self.assertEqual(conversation.messages[0].role, "customer")
        self.assertEqual(
            conversation.messages[0].content,
            "My pet hospital stay cost 1800, so why did you only reimburse 800?",
        )
        self.assertEqual(
            conversation.expected_risks, ["SEM-002", "SEM-003", "RAG-001"]
        )


if __name__ == "__main__":
    unittest.main()
