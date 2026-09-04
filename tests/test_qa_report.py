from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.conversation import load_conversation
from claimguard.qa import generate_qa_report
from claimguard.rules import load_rule_catalog
from claimguard.semantic_judge import SemanticJudgeError, SemanticJudgment


class FakeJudge:
    def __init__(self, judgments):
        self.judgments = judgments

    def judge(self, conversation):
        return self.judgments


class QAReportTest(unittest.TestCase):
    def test_appends_quote_backed_semantic_findings_in_judge_order(self):
        conversation = load_conversation(
            Path("examples/conversations/zh-semantic-qa.json")
        )
        report = generate_qa_report(
            conversation,
            load_rule_catalog(),
            semantic_judge=FakeJudge(
                [
                    SemanticJudgment(
                        rule_id="SEM-005",
                        violated=True,
                        evidence="您的理赔明天一定到账。",
                        reasoning="客服作出了无依据的到账承诺。",
                        recommendation="说明处理时效需要以审核结果为准。",
                        confidence="high",
                    ),
                    SemanticJudgment(
                        rule_id="SEM-004",
                        violated=True,
                        evidence="审核结果就是这样，您自己看条款。",
                        reasoning="客服没有回应客户的投诉或安抚担忧。",
                        recommendation="先承认客户的担忧，再说明下一步处理方式。",
                        confidence="medium",
                    ),
                ]
            ),
        )

        self.assertEqual(
            [finding.rule_id for finding in report.findings], ["SEM-005", "SEM-004"]
        )
        finding = report.findings[0]
        self.assertEqual(finding.judge, "semantic_llm")
        self.assertEqual(finding.confidence, "high")
        self.assertEqual(finding.reasoning, "客服作出了无依据的到账承诺。")
        self.assertIsNone(finding.grounding)

    def test_rejects_semantic_evidence_that_is_only_an_agent_message_fragment(self):
        conversation = load_conversation(
            Path("examples/conversations/zh-semantic-qa.json")
        )

        with self.assertRaises(SemanticJudgeError):
            generate_qa_report(
                conversation,
                load_rule_catalog(),
                semantic_judge=FakeJudge(
                    [
                        SemanticJudgment(
                            rule_id="SEM-005",
                            violated=True,
                            evidence="明天一定到账。",
                            reasoning="客服作出了无依据的到账承诺。",
                            recommendation="说明处理时效需要以审核结果为准。",
                            confidence="high",
                        )
                    ]
                ),
            )

    def test_skips_semantic_judgment_for_an_existing_deterministic_finding(self):
        conversation = load_conversation(
            Path("examples/conversations/claim-amount-dispute.json")
        )
        report = generate_qa_report(
            conversation,
            load_rule_catalog(),
            semantic_judge=FakeJudge(
                [
                    SemanticJudgment(
                        rule_id="SEM-002",
                        violated=True,
                        evidence="The review team approved it this way. That is the final result.",
                        reasoning="客服没有回答客户关于赔付金额的核心问题。",
                        recommendation="解释审核依据和赔付计算方式。",
                        confidence="high",
                    )
                ]
            ),
        )

        self.assertEqual(
            [finding.rule_id for finding in report.findings],
            ["SEM-002", "SEM-003", "RAG-001"],
        )
        self.assertIsNone(report.findings[0].judge)

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
        report_dict = report.to_dict()
        self.assertIsNone(report_dict["findings"][0]["reasoning"])
        self.assertIsNone(report_dict["findings"][0]["confidence"])
        self.assertIsNone(report_dict["findings"][0]["judge"])

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
