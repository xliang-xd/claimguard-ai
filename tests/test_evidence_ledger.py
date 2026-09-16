from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.agent_runtime.evidence import EvidenceLedger, EvidenceRecord


def evidence_record(clause_id="18"):
    return EvidenceRecord(
        clause_id=clause_id,
        title="等待期",
        content="等待期内疾病治疗不予赔付。",
        source_path="policy.md",
        retrieval_score=0.8,
        rerank_score=0.9,
    )


class EvidenceLedgerTest(unittest.TestCase):
    def test_snapshot_returns_recorded_evidence_in_append_order(self):
        ledger = EvidenceLedger()
        first = evidence_record("18")
        second = evidence_record("19")

        ledger.record([first])
        ledger.record([second])

        self.assertEqual(ledger.snapshot(), (first, second))

    def test_clear_removes_all_recorded_evidence(self):
        ledger = EvidenceLedger()
        ledger.record([evidence_record()])

        ledger.clear()

        self.assertEqual(ledger.snapshot(), ())


if __name__ == "__main__":
    unittest.main()
