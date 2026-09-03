from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.conversation import Conversation, Message, load_conversation
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

    def test_detects_incomplete_chinese_clause_explanations(self):
        cases = (
            (
                "RAG-001",
                "我的宠物住院花了1800元，为什么理赔只赔800元？",
                "依据条款12，免赔额。",
            ),
            (
                "RAG-002",
                "保单刚生效10天，为什么等待期内的疾病治疗不赔？",
                "依据条款18，等待期。",
            ),
            (
                "RAG-003",
                "为什么我家宠物的皮肤病不在保障范围，不能理赔？",
                "依据条款24，保障范围。",
            ),
            (
                "RAG-004",
                "摔伤算不算意外事故，意外事故具体怎么定义？",
                "依据条款31，突发事故。",
            ),
            (
                "RAG-005",
                "我家宠物的疾病不在保障范围被拒赔，依据哪条保单条款？",
                "依据条款12，疾病不赔。",
            ),
        )

        for rule_id, customer_text, agent_text in cases:
            with self.subTest(rule_id=rule_id):
                self.assertEqual(
                    [match.rule_id for match in run_rules(self._conversation(customer_text, agent_text))],
                    [rule_id],
                )

    def test_accepts_complete_chinese_clause_explanations(self):
        cases = (
            (
                "我的宠物住院花了1800元，为什么理赔只赔800元？",
                "依据条款12，计算赔付金额前会先扣除保单约定的免赔额。",
            ),
            (
                "保单刚生效10天，为什么等待期内的疾病治疗不赔？",
                "依据条款18，等待期内开始的疾病治疗不予赔付。",
            ),
            (
                "为什么我家宠物的皮肤病不在保障范围，不能理赔？",
                "依据条款24，只有列入疾病保障清单的疾病才可以申请医疗赔付。",
            ),
            (
                "摔伤算不算意外事故，意外事故具体怎么定义？",
                "依据条款31，意外事故必须突发、外来、非故意且直接导致宠物身体受伤。",
            ),
            (
                "我家宠物的疾病不在保障范围被拒赔，依据哪条保单条款？",
                "依据条款24，只有列入疾病保障清单的疾病才可以申请医疗赔付。",
            ),
        )

        for customer_text, agent_text in cases:
            with self.subTest(customer_text=customer_text):
                self.assertEqual(
                    run_rules(self._conversation(customer_text, agent_text)), []
                )

    def _conversation(self, customer_text, agent_text):
        return Conversation(
            id="chinese-rule-test",
            scenario="Chinese policy explanation",
            messages=[
                Message(role="customer", content=customer_text),
                Message(role="agent", content=agent_text),
            ],
            expected_risks=[],
        )


if __name__ == "__main__":
    unittest.main()
