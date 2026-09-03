import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.knowledge import (
    IndexedClause,
    KnowledgeError,
    KnowledgeIndex,
    PolicyClause,
    load_knowledge_index,
    parse_policy_markdown,
    save_knowledge_index,
)


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

        self.assertEqual(load_knowledge_index(index_path), index)

    def test_load_rejects_missing_clause_fields(self):
        index_path = self.write_index_payload(
            {
                "schema_version": 1,
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
        index_path = self.write_index_payload({"schema_version": 1, "clauses": []})

        with self.assertRaises(KnowledgeError):
            load_knowledge_index(index_path)

    def test_load_rejects_non_finite_vector_values(self):
        index_path = self.directory / "index.json"
        index_path.write_text(
            '{"schema_version": 1, "clauses": [{"id": "12", "title": "免赔额", '
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
