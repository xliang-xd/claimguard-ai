from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.knowledge import PolicyClause, RetrievedClause
from claimguard.reranking import RerankingError, rerank_clauses


class StaticReranker:
    model = "test-reranker"

    def __init__(self, scores):
        self.scores = scores
        self.calls = []

    def rerank(self, query, documents):
        self.calls.append((query, documents))
        return self.scores


class FailingReranker:
    model = "test-reranker"

    def rerank(self, query, documents):
        raise RerankingError("客户私密问题：条款私密正文")


def candidates():
    return [
        RetrievedClause(
            clause=PolicyClause("2", "免赔额", "先扣除免赔额。", "policy.md"),
            score=0.8,
        ),
        RetrievedClause(
            clause=PolicyClause("18", "等待期", "等待期内疾病治疗不赔。", "policy.md"),
            score=0.4,
        ),
    ]


class RerankClausesTest(unittest.TestCase):
    def test_rerank_orders_scores_and_preserves_retrieval_score(self):
        reranker = StaticReranker([0.2, 0.9])

        result = rerank_clauses("等待期", candidates(), reranker)

        self.assertEqual([item.clause.id for item in result], ["18", "2"])
        self.assertEqual(result[0].rerank_score, 0.9)
        self.assertEqual(result[0].retrieval_score, 0.4)
        self.assertEqual(
            reranker.calls,
            [("等待期", ["先扣除免赔额。", "等待期内疾病治疗不赔。"])],
        )

    def test_rerank_breaks_score_ties_by_retrieval_score_then_clause_id(self):
        tied_candidates = [
            RetrievedClause(
                clause=PolicyClause("2", "免赔额", "甲", "policy.md"), score=0.5
            ),
            RetrievedClause(
                clause=PolicyClause("18", "等待期", "乙", "policy.md"), score=0.7
            ),
            RetrievedClause(
                clause=PolicyClause("3", "范围", "丙", "policy.md"), score=0.7
            ),
        ]

        result = rerank_clauses("查询", tied_candidates, StaticReranker([0.6, 0.6, 0.6]))

        self.assertEqual([item.clause.id for item in result], ["18", "3", "2"])

    def test_rerank_rejects_blank_query_without_calling_provider(self):
        reranker = StaticReranker([0.9, 0.8])

        with self.assertRaisesRegex(RerankingError, "重排查询"):
            rerank_clauses("  ", candidates(), reranker)

        self.assertEqual(reranker.calls, [])

    def test_rerank_rejects_duplicate_clause_ids_without_calling_provider(self):
        duplicate_candidates = candidates()
        duplicate_candidates[1] = RetrievedClause(
            clause=PolicyClause("2", "等待期", "等待期内疾病治疗不赔。", "policy.md"),
            score=0.4,
        )
        reranker = StaticReranker([0.2, 0.9])

        with self.assertRaisesRegex(RerankingError, "条款 ID"):
            rerank_clauses("等待期", duplicate_candidates, reranker)

        self.assertEqual(reranker.calls, [])

    def test_rerank_rejects_mismatched_score_count(self):
        with self.assertRaisesRegex(RerankingError, "数量"):
            rerank_clauses("等待期", candidates(), StaticReranker([0.9]))

    def test_rerank_rejects_boolean_and_non_finite_scores(self):
        for score in (True, float("nan"), float("inf"), float("-inf")):
            with self.subTest(score=score):
                with self.assertRaisesRegex(RerankingError, "重排分数"):
                    rerank_clauses("等待期", candidates(), StaticReranker([0.9, score]))

    def test_rerank_rejects_oversized_integer_scores(self):
        oversized_score = 10**10000

        with self.assertRaisesRegex(RerankingError, "重排分数"):
            rerank_clauses("等待期", candidates(), StaticReranker([0.9, oversized_score]))

        invalid_candidates = candidates()
        invalid_candidates[0] = RetrievedClause(
            clause=invalid_candidates[0].clause, score=oversized_score
        )
        with self.assertRaisesRegex(RerankingError, "召回分数"):
            rerank_clauses("等待期", invalid_candidates, StaticReranker([0.9, 0.8]))

    def test_rerank_rejects_boolean_and_non_finite_retrieval_scores(self):
        for score in (True, float("nan"), float("inf"), float("-inf")):
            with self.subTest(score=score):
                invalid_candidates = candidates()
                invalid_candidates[0] = RetrievedClause(
                    clause=invalid_candidates[0].clause, score=score
                )
                reranker = StaticReranker([0.9, 0.8])

                with self.assertRaisesRegex(RerankingError, "召回分数"):
                    rerank_clauses("等待期", invalid_candidates, reranker)

                self.assertEqual(reranker.calls, [])

    def test_rerank_hides_provider_error_details(self):
        with self.assertRaises(RerankingError) as context:
            rerank_clauses("客户私密问题", candidates(), FailingReranker())

        error_text = str(context.exception)
        self.assertEqual(error_text, "重排请求失败")
        self.assertNotIn("客户私密问题", error_text)
        self.assertNotIn("条款私密正文", error_text)


if __name__ == "__main__":
    unittest.main()
