import json
from pathlib import Path
import unittest


_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "evaluations" / "citation-judge-zh.json"
)


class CitationEvaluationFixtureTest(unittest.TestCase):
    def load_fixture(self):
        self.assertTrue(_FIXTURE_PATH.is_file())
        return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_fixture_covers_the_four_required_chinese_categories(self):
        fixture = self.load_fixture()

        self.assertEqual(fixture["language"], "zh-CN")
        self.assertEqual(
            {case["category"] for case in fixture["cases"]},
            {"supported", "incomplete", "wrong_clause", "no_evidence"},
        )
        self.assertEqual(len(fixture["cases"]), 4)

    def test_fixture_expected_verdicts_match_each_category(self):
        fixture = self.load_fixture()
        cases_by_category = {case["category"]: case for case in fixture["cases"]}

        self.assertEqual(
            cases_by_category["supported"]["expected"],
            {"status": "supported", "citations": ["PET-WAIT-30"]},
        )
        self.assertEqual(
            cases_by_category["incomplete"]["expected"],
            {"status": "insufficient_evidence", "citations": []},
        )
        self.assertEqual(
            cases_by_category["wrong_clause"]["expected"],
            {"status": "unsupported", "citations": []},
        )
        self.assertEqual(
            cases_by_category["no_evidence"]["expected"],
            {"status": "insufficient_evidence", "citations": []},
        )

    def test_fixture_contains_only_synthetic_chinese_pet_insurance_data(self):
        fixture = self.load_fixture()

        for case in fixture["cases"]:
            self.assertIsInstance(case["draft"], str)
            self.assertTrue(case["draft"].strip())
            self.assertIsInstance(case["evidence"], list)
            for evidence in case["evidence"]:
                self.assertEqual(
                    set(evidence),
                    {"clause_id", "title", "content"},
                )
                self.assertTrue(all(isinstance(value, str) and value for value in evidence.values()))


if __name__ == "__main__":
    unittest.main()
