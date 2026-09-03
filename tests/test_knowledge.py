import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import claimguard
from claimguard.knowledge import (
    IndexedClause,
    KnowledgeError,
    KnowledgeIndex,
    PolicyClause,
    build_knowledge_index,
    load_knowledge_index,
    parse_policy_markdown,
    retrieve_clauses,
    save_knowledge_index,
)


class StaticEmbeddingClient:
    def __init__(self, vectors, model="test-model"):
        self.vectors = vectors
        self.model = model

    def embed(self, texts):
        return [self.vectors[text] for text in texts]


class KnowledgeMetadataTest(unittest.TestCase):
    def test_package_and_project_metadata_match_v0_3_release(self):
        project_metadata = (
            Path(__file__).resolve().parents[1] / "pyproject.toml"
        ).read_text(encoding="utf-8")
        project_version_match = re.search(
            r'^version\s*=\s*"(?P<version>[^"]+)"\s*$',
            project_metadata,
            flags=re.MULTILINE,
        )

        self.assertIsNotNone(project_version_match)
        project_version = project_version_match.group("version")
        self.assertEqual(claimguard.__version__, "0.3.0")
        self.assertEqual(project_version, "0.3.0")
        self.assertEqual(project_version, claimguard.__version__)


class KnowledgeTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.directory = Path(self.temporary_directory.name)

    def write_policy(self, content: str) -> Path:
        policy = self.directory / "policy.md"
        policy.write_text(content, encoding="utf-8")
        return policy

    def write_index_payload(self, payload: dict) -> Path:
        index_path = self.directory / "index.json"
        index_path.write_text(json.dumps(payload), encoding="utf-8")
        return index_path

    def test_parses_chinese_policy_clause_heading_and_source_path(self):
        policy = self.write_policy(
            "## 条款 12：免赔额\n赔付前会先扣除保单约定的免赔额。\n"
            "\n## 条款 18：等待期\n等待期内开始的疾病治疗不予赔付。\n"
        )

        clauses = parse_policy_markdown(policy)

        self.assertEqual([clause.id for clause in clauses], ["12", "18"])
        self.assertEqual(clauses[0].title, "免赔额")
        self.assertIn("扣除", clauses[0].content)
        self.assertEqual(clauses[0].source_path, str(policy))

    def test_rejects_duplicate_clause_ids(self):
        policy = self.write_policy(
            "## 条款 12: 免赔额\n赔付前扣除免赔额。\n"
            "\n## 条款 12：重复条款\n这是重复条款。\n"
        )

        with self.assertRaises(KnowledgeError):
            parse_policy_markdown(policy)

    def test_rejects_clause_without_content(self):
        policy = self.write_policy("## 条款 12：免赔额\n\n")

        with self.assertRaises(KnowledgeError):
            parse_policy_markdown(policy)

    def test_parses_committed_chinese_policy_fixture(self):
        clauses = parse_policy_markdown(
            Path("data/knowledge/petcare-plus-policy-zh.md")
        )

        self.assertEqual([clause.id for clause in clauses], ["12", "18", "24", "31"])
        self.assertEqual(clauses[2].title, "疾病保障范围")

    def test_index_round_trip_preserves_literal_vectors(self):
        index = KnowledgeIndex(
            clauses=[
                IndexedClause(
                    clause=PolicyClause(
                        id="12",
                        title="免赔额",
                        content="赔付前会先扣除保单约定的免赔额。",
                        source_path="data/knowledge/petcare-plus-policy-zh.md",
                    ),
                    vector=[0.125, -0.75],
                )
            ]
        )
        index_path = self.directory / "knowledge-index.json"

        save_knowledge_index(index, index_path)

        payload = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["embedding_model"], "legacy-local")
        self.assertEqual(payload["dimensions"], 2)
        self.assertEqual(load_knowledge_index(index_path), index)

    def test_loads_task_1_schema_v1_json_without_embedding_metadata(self):
        index_path = self.write_index_payload(
            {
                "schema_version": 1,
                "clauses": [
                    {
                        "id": "12",
                        "title": "免赔额",
                        "content": "赔付前扣免赔额。",
                        "source_path": "policy.md",
                        "vector": [0.25, -0.5],
                    }
                ],
            }
        )

        index = load_knowledge_index(index_path)

        self.assertEqual(index.schema_version, 1)
        self.assertEqual(index.embedding_model, "legacy-local")
        self.assertEqual(index.dimensions, 2)
        self.assertEqual(index.clauses[0].vector, [0.25, -0.5])

    def test_builds_index_from_complete_clause_contents(self):
        clauses = [
            PolicyClause("12", "免赔额", "赔付前扣免赔额", "policy.md"),
            PolicyClause("18", "等待期", "等待期内不赔", "policy.md"),
        ]

        index = build_knowledge_index(
            clauses,
            StaticEmbeddingClient(
                {
                    "赔付前扣免赔额": [1.0, 0.0],
                    "等待期内不赔": [0.0, 1.0],
                }
            ),
        )

        self.assertEqual(index.schema_version, 1)
        self.assertEqual(index.dimensions, 2)
        self.assertEqual(
            [indexed_clause.vector for indexed_clause in index.clauses],
            [[1.0, 0.0], [0.0, 1.0]],
        )

    def test_rejects_embedding_count_that_does_not_match_clauses(self):
        clauses = [PolicyClause("12", "免赔额", "赔付前扣免赔额", "policy.md")]

        class IncompleteEmbeddingClient:
            def embed(self, texts):
                return []

        with self.assertRaises(KnowledgeError):
            build_knowledge_index(clauses, IncompleteEmbeddingClient())

    def test_retrieves_highest_cosine_clause_and_breaks_ties_by_id(self):
        index = KnowledgeIndex(
            schema_version=1,
            embedding_model="test-model",
            dimensions=2,
            clauses=[
                IndexedClause(PolicyClause("18", "等待期", "等待期内不赔", "policy.md"), [0.0, 1.0]),
                IndexedClause(PolicyClause("12", "免赔额", "赔付前扣免赔额", "policy.md"), [1.0, 0.0]),
            ],
        )

        result = retrieve_clauses(
            "为什么只赔一部分",
            index,
            StaticEmbeddingClient({"为什么只赔一部分": [1.0, 0.0]}),
            top_k=1,
        )

        self.assertEqual(result[0].clause.id, "12")
        self.assertEqual(result[0].score, 1.0)

    def test_retrieval_rejects_query_vector_with_wrong_dimension(self):
        index = KnowledgeIndex(
            schema_version=1,
            embedding_model="test-model",
            dimensions=2,
            clauses=[
                IndexedClause(PolicyClause("12", "免赔额", "赔付前扣免赔额", "policy.md"), [1.0, 0.0])
            ],
        )

        with self.assertRaises(KnowledgeError):
            retrieve_clauses(
                "为什么只赔一部分",
                index,
                StaticEmbeddingClient({"为什么只赔一部分": [1.0]}),
            )

    def test_retrieval_rejects_embedding_model_mismatch_before_querying(self):
        index = KnowledgeIndex(
            schema_version=1,
            embedding_model="qwen3.7-text-embedding",
            dimensions=2,
            clauses=[
                IndexedClause(PolicyClause("12", "免赔额", "赔付前扣免赔额", "policy.md"), [1.0, 0.0])
            ],
        )

        with self.assertRaisesRegex(
            KnowledgeError,
            "Embedding model does not match the knowledge index",
        ):
            retrieve_clauses(
                "为什么只赔一部分",
                index,
                StaticEmbeddingClient(
                    {"为什么只赔一部分": [1.0, 0.0]},
                    model="another-1024-dimensional-model",
                ),
            )

    def test_retrieval_reports_invalid_index_entries_as_knowledge_errors(self):
        index = KnowledgeIndex(
            schema_version=1,
            embedding_model="test-model",
            dimensions=2,
            clauses=[object()],
        )

        with self.assertRaises(KnowledgeError):
            retrieve_clauses(
                "为什么只赔一部分",
                index,
                StaticEmbeddingClient({"为什么只赔一部分": [1.0, 0.0]}),
            )

    def test_load_rejects_missing_clause_fields(self):
        index_path = self.write_index_payload(
            {
                "schema_version": 1,
                "embedding_model": "test-model",
                "dimensions": 2,
                "clauses": [
                    {
                        "id": "12",
                        "title": "免赔额",
                        "content": "赔付前扣除免赔额。",
                        "source_path": "policy.md",
                    }
                ],
            }
        )

        with self.assertRaises(KnowledgeError):
            load_knowledge_index(index_path)

    def test_load_rejects_empty_clause_list(self):
        index_path = self.write_index_payload(
            {
                "schema_version": 1,
                "embedding_model": "test-model",
                "dimensions": 2,
                "clauses": [],
            }
        )

        with self.assertRaises(KnowledgeError):
            load_knowledge_index(index_path)

    def test_load_rejects_non_finite_vector_values(self):
        index_path = self.directory / "index.json"
        index_path.write_text(
            '{"schema_version": 1, "embedding_model": "test-model", "dimensions": 2, '
            '"clauses": [{"id": "12", "title": "免赔额", '
            '"content": "赔付前扣除免赔额。", "source_path": "policy.md", '
            '"vector": [NaN]}]}',
            encoding="utf-8",
        )

        with self.assertRaises(KnowledgeError):
            load_knowledge_index(index_path)

    def test_load_rejects_vectors_with_disagreeing_lengths(self):
        index_path = self.write_index_payload(
            {
                "schema_version": 1,
                "embedding_model": "test-model",
                "dimensions": 2,
                "clauses": [
                    {
                        "id": "12",
                        "title": "免赔额",
                        "content": "赔付前扣除免赔额。",
                        "source_path": "policy.md",
                        "vector": [0.1, 0.2],
                    },
                    {
                        "id": "18",
                        "title": "等待期",
                        "content": "等待期内疾病治疗不予赔付。",
                        "source_path": "policy.md",
                        "vector": [0.3],
                    },
                ],
            }
        )

        with self.assertRaises(KnowledgeError):
            load_knowledge_index(index_path)


if __name__ == "__main__":
    unittest.main()
