from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.conversation import Conversation, Message, load_conversation
from claimguard.knowledge import IndexedClause, KnowledgeIndex, PolicyClause
from claimguard.qa import generate_qa_report
from claimguard.rule_runner import RuleMatch
from claimguard.rules import load_rule_catalog


class LiteralEmbeddingClient:
    model = "literal-test"

    def __init__(self, vectors):
        self.vectors = vectors

    def embed(self, texts):
        return [self.vectors[text] for text in texts]


class RecordingEmbeddingClient:
    model = "literal-test"

    def __init__(self):
        self.calls = []

    def embed(self, texts):
        self.calls.append(texts)
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


class ChineseRAGTest(unittest.TestCase):
    def setUp(self):
        self.index = KnowledgeIndex(
            schema_version=1,
            embedding_model="literal-test",
            dimensions=4,
            clauses=[
                IndexedClause(
                    PolicyClause(
                        "12",
                        "免赔额",
                        "对符合赔付条件的住院治疗，保险人在计算可赔付金额前，会先扣除保单约定的免赔额。",
                        "data/knowledge/petcare-plus-policy-zh.md",
                    ),
                    [1.0, 0.0, 0.0, 0.0],
                ),
                IndexedClause(
                    PolicyClause(
                        "18",
                        "等待期",
                        "等待期内开始的疾病治疗不予赔付，除非保单特别约定了例外情形。",
                        "data/knowledge/petcare-plus-policy-zh.md",
                    ),
                    [0.0, 1.0, 0.0, 0.0],
                ),
                IndexedClause(
                    PolicyClause(
                        "24",
                        "疾病保障范围",
                        "只有列入疾病保障清单的疾病，才可以申请疾病医疗赔付。",
                        "data/knowledge/petcare-plus-policy-zh.md",
                    ),
                    [0.0, 0.0, 1.0, 0.0],
                ),
                IndexedClause(
                    PolicyClause(
                        "31",
                        "意外事故定义",
                        "意外事故是指突发、外来、非故意且直接导致被保险宠物身体受伤的事件。",
                        "data/knowledge/petcare-plus-policy-zh.md",
                    ),
                    [0.0, 0.0, 0.0, 1.0],
                ),
            ],
        )
        self.client = LiteralEmbeddingClient(
            {
                "我的宠物住院花了1800元，为什么理赔只赔800元？ Claim amount dispute: deductible": [
                    1.0,
                    0.0,
                    0.0,
                    0.0,
                ],
                "保单刚生效10天，为什么等待期内的疾病治疗不赔？ Pre-policy or waiting-period treatment denial": [
                    0.0,
                    1.0,
                    0.0,
                    0.0,
                ],
                "为什么我家宠物的皮肤病不在保障范围，不能理赔？ Disease outside policy coverage": [
                    0.0,
                    0.0,
                    1.0,
                    0.0,
                ],
                "摔伤算不算意外事故，意外事故具体怎么定义？ Accident definition explanation": [
                    0.0,
                    0.0,
                    0.0,
                    1.0,
                ],
                "我家宠物的疾病不在保障范围被拒赔，依据哪条保单条款？ Dynamic clause citation for pet insurance denial": [
                    0.0,
                    0.0,
                    1.0,
                    0.0,
                ],
            }
        )

    def test_detects_deductible_dispute_and_attaches_clause_evidence(self):
        finding = self._finding("zh-deductible-dispute.json", "RAG-001")

        self.assertEqual(finding.grounding.clause_id, "12")
        self.assertEqual(finding.grounding.clause_title, "免赔额")
        self.assertIn("扣除保单约定的免赔额", finding.grounding.clause_text)

    def test_detects_waiting_period_denial_and_attaches_clause_evidence(self):
        finding = self._finding("zh-waiting-period-denial.json", "RAG-002")

        self.assertEqual(finding.grounding.clause_id, "18")
        self.assertEqual(finding.grounding.clause_title, "等待期")
        self.assertIn("等待期内", finding.grounding.clause_text)

    def test_detects_coverage_denial_and_attaches_clause_evidence(self):
        finding = self._finding("zh-coverage-denial.json", "RAG-003")

        self.assertEqual(finding.grounding.clause_id, "24")
        self.assertEqual(finding.grounding.clause_title, "疾病保障范围")
        self.assertIn("疾病保障清单", finding.grounding.clause_text)

    def test_detects_accident_definition_and_attaches_clause_evidence(self):
        finding = self._finding("zh-accident-definition.json", "RAG-004")

        self.assertEqual(finding.grounding.clause_id, "31")
        self.assertEqual(finding.grounding.clause_title, "意外事故定义")
        self.assertIn("突发、外来、非故意", finding.grounding.clause_text)

    def test_detects_denial_citation_and_attaches_clause_evidence(self):
        finding = self._finding("zh-denial-citation.json", "RAG-005")

        self.assertEqual(finding.grounding.clause_id, "24")
        self.assertEqual(finding.grounding.clause_title, "疾病保障范围")
        self.assertIn("疾病保障清单", finding.grounding.clause_text)

    def test_denial_citation_uses_waiting_period_clause_when_that_is_the_reason(self):
        conversation = Conversation(
            id="waiting-period-citation",
            scenario="Waiting-period denial clause citation",
            messages=[
                Message(
                    role="customer",
                    content="等待期内的疾病治疗为什么被拒赔，依据哪条保单条款？",
                ),
                Message(
                    role="agent",
                    content="因为疾病治疗发生在等待期内，所以不予赔付。",
                ),
            ],
            expected_risks=[],
        )
        self.client.vectors[
            "等待期内的疾病治疗为什么被拒赔，依据哪条保单条款？ Dynamic clause citation for pet insurance denial"
        ] = [0.0, 1.0, 0.0, 0.0]

        report = generate_qa_report(
            conversation,
            load_rule_catalog(),
            knowledge_index=self.index,
            embedding_client=self.client,
        )

        finding = next(item for item in report.findings if item.rule_id == "RAG-005")
        self.assertEqual(finding.grounding.clause_id, "18")

    def test_accepts_waiting_period_citation_that_matches_the_denial_reason(self):
        conversation = Conversation(
            id="waiting-period-citation-complete",
            scenario="Complete waiting-period denial citation",
            messages=[
                Message(
                    role="customer",
                    content="等待期内的疾病治疗为什么被拒赔，依据哪条保单条款？",
                ),
                Message(
                    role="agent",
                    content="依据条款18，等待期内开始的疾病治疗不予赔付。",
                ),
            ],
            expected_risks=[],
        )

        report = generate_qa_report(conversation, load_rule_catalog())

        self.assertNotIn("RAG-005", [item.rule_id for item in report.findings])

    def test_retrieval_uses_deductible_message_after_an_unrelated_opener(self):
        conversation = Conversation(
            id="deductible-after-opener",
            scenario="Deductible question after unrelated opener",
            messages=[
                Message(role="customer", content="你好，我想咨询一下续保流程。"),
                Message(role="agent", content="请问您想了解哪方面？"),
                Message(role="customer", content="为什么理赔只赔800元？"),
                Message(role="agent", content="我暂时无法确认。"),
            ],
            expected_risks=[],
        )
        client = RecordingEmbeddingClient()

        generate_qa_report(
            conversation,
            load_rule_catalog(),
            knowledge_index=self.index,
            embedding_client=client,
        )

        self.assertEqual(
            client.calls,
            [["为什么理赔只赔800元？ Claim amount dispute: deductible"]],
        )

    def test_retrieval_uses_waiting_period_message_after_an_unrelated_opener(self):
        conversation = Conversation(
            id="waiting-period-after-opener",
            scenario="Waiting-period question after unrelated opener",
            messages=[
                Message(role="customer", content="你好，我想更新联系信息。"),
                Message(role="agent", content="可以，请告诉我您的需求。"),
                Message(
                    role="customer",
                    content="为什么等待期内的疾病治疗不赔？",
                ),
                Message(role="agent", content="结果就是不能赔。"),
            ],
            expected_risks=[],
        )
        client = RecordingEmbeddingClient()

        generate_qa_report(
            conversation,
            load_rule_catalog(),
            knowledge_index=self.index,
            embedding_client=client,
        )

        self.assertEqual(
            client.calls,
            [["为什么等待期内的疾病治疗不赔？ Pre-policy or waiting-period treatment denial"]],
        )

    def test_does_not_retrieve_for_nonknowledge_or_unconfigured_knowledge_findings(self):
        client = RecordingEmbeddingClient()
        catalog = load_rule_catalog()
        semantic_conversation = Conversation(
            id="semantic-only",
            scenario="Semantic-only finding",
            messages=[
                Message(role="customer", content="Hello."),
                Message(role="agent", content="That is the final result."),
            ],
            expected_risks=[],
        )

        semantic_report = generate_qa_report(
            semantic_conversation,
            catalog,
            knowledge_index=self.index,
            embedding_client=client,
        )
        knowledge_conversation = load_conversation(
            Path("examples/conversations/zh-deductible-dispute.json")
        )
        without_index = generate_qa_report(
            knowledge_conversation, catalog, embedding_client=client
        )
        without_client = generate_qa_report(
            knowledge_conversation, catalog, knowledge_index=self.index
        )

        with patch("claimguard.qa.run_rules", return_value=[RuleMatch("PROC-001", "")]):
            process_report = generate_qa_report(
                semantic_conversation,
                catalog,
                knowledge_index=self.index,
                embedding_client=client,
            )

        self.assertEqual([finding.rule_id for finding in semantic_report.findings], ["SEM-003"])
        self.assertIsNone(semantic_report.findings[0].grounding)
        self.assertIsNone(without_index.findings[0].grounding)
        self.assertIsNone(without_client.findings[0].grounding)
        self.assertEqual([finding.rule_id for finding in process_report.findings], ["PROC-001"])
        self.assertIsNone(process_report.findings[0].grounding)
        self.assertEqual(client.calls, [])

    def _finding(self, fixture_name, rule_id):
        report = generate_qa_report(
            load_conversation(Path("examples/conversations") / fixture_name),
            load_rule_catalog(),
            knowledge_index=self.index,
            embedding_client=self.client,
        )

        self.assertEqual([item.rule_id for item in report.findings], [rule_id])
        return report.findings[0]


if __name__ == "__main__":
    unittest.main()
