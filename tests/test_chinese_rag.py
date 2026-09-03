from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.conversation import load_conversation
from claimguard.knowledge import IndexedClause, KnowledgeIndex, PolicyClause
from claimguard.qa import generate_qa_report
from claimguard.rules import load_rule_catalog


class LiteralEmbeddingClient:
    model = "literal-test"

    def __init__(self, vectors):
        self.vectors = vectors

    def embed(self, texts):
        return [self.vectors[text] for text in texts]


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
