import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.rules import load_rule_catalog


class RuleCatalogTest(unittest.TestCase):
    def test_v1_rule_catalog_covers_expected_qa_capabilities(self):
        catalog = load_rule_catalog()

        self.assertEqual(len(catalog.rules), 12)
        self.assertEqual(
            {rule.category for rule in catalog.rules},
            {
                "semantic",
                "process",
                "knowledge_grounded",
            },
        )
        self.assertTrue(catalog.get("RAG-005").hero_case)
        self.assertEqual(catalog.get("RAG-005").risk_level, "high")
        self.assertEqual(
            catalog.get("RAG-005").detection,
            "intent + rag + citation judge",
        )


if __name__ == "__main__":
    unittest.main()
