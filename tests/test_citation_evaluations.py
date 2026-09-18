import json
from pathlib import Path
import unittest

from claimguard.agent_runtime.evidence import EvidenceRecord
from claimguard.citation_judge import CitationVerdict


_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "evaluations" / "citation-judge-zh.json"
)


class LocalCitationJudge:
    """A deterministic, offline verdict layer for the synthetic evaluation set."""

    def judge(
        self, draft: str, evidence: tuple[EvidenceRecord, ...]
    ) -> CitationVerdict:
        if not evidence:
            return CitationVerdict(
                status="insufficient_evidence",
                citations=(),
                reason_code="insufficient_evidence",
            )
        if any(
            "等待期" in draft
            and "30 日" in draft
            and "等待期" in record.title
            and "30 日" in record.content
            for record in evidence
        ):
            return CitationVerdict(
                status="supported",
                citations=(evidence[0].clause_id,),
                reason_code="citation_supported",
            )
        if any(
            "90%" in draft and "免赔额" in record.content and "免赔额" not in draft
            for record in evidence
        ):
            return CitationVerdict(
                status="insufficient_evidence",
                citations=(),
                reason_code="insufficient_evidence",
            )
        return CitationVerdict(
            status="unsupported",
            citations=(),
            reason_code="citation_unsupported",
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

    def test_each_synthetic_case_is_evaluated_by_an_injected_local_judge(self):
        fixture = self.load_fixture()
        judge = LocalCitationJudge()

        for case in fixture["cases"]:
            with self.subTest(category=case["category"]):
                evidence = tuple(
                    EvidenceRecord(
                        source_path="synthetic-policy.md",
                        retrieval_score=1.0,
                        rerank_score=1.0,
                        **record,
                    )
                    for record in case["evidence"]
                )

                verdict = judge.judge(case["draft"], evidence)

                self.assertEqual(
                    {"status": verdict.status, "citations": list(verdict.citations)},
                    case["expected"],
                )


if __name__ == "__main__":
    unittest.main()
