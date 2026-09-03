from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.conversation import load_conversation
from claimguard.qa import generate_qa_report
from claimguard.rules import load_rule_catalog


class QAReportTest(unittest.TestCase):
    def test_generates_report_from_expected_risks_with_score_and_findings(self):
        conversation = load_conversation(
            Path("examples/conversations/claim-amount-dispute.json")
        )
        report = generate_qa_report(conversation, load_rule_catalog())

        self.assertEqual(report.conversation_id, "claim-amount-dispute-001")
        self.assertEqual(report.score, 70)
        self.assertEqual(
            [finding.rule_id for finding in report.findings],
            ["SEM-002", "SEM-003", "RAG-001"],
        )
        rag_finding = next(
            finding for finding in report.findings if finding.rule_id == "RAG-001"
        )
        self.assertIsNone(rag_finding.grounding)
        self.assertEqual(report.findings[0].risk_level, "critical")
        self.assertIn(
            "review team approved it this way", report.findings[0].evidence.lower()
        )

    def test_report_findings_do_not_depend_on_expected_risks_fixture_field(self):
        conversation = load_conversation(
            Path("examples/conversations/claim-amount-dispute.json")
        )
        conversation_without_expected = type(conversation)(
            id=conversation.id,
            scenario=conversation.scenario,
            messages=conversation.messages,
            expected_risks=[],
        )

        report = generate_qa_report(conversation_without_expected, load_rule_catalog())

        self.assertEqual(
            [finding.rule_id for finding in report.findings],
            ["SEM-002", "SEM-003", "RAG-001"],
        )


if __name__ == "__main__":
    unittest.main()
