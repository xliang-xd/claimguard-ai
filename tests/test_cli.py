import json
from pathlib import Path
import subprocess
import sys
import unittest


class CLITest(unittest.TestCase):
    def test_cli_outputs_qa_report_json_for_conversation_fixture(self):
        command = [
            sys.executable,
            "-m",
            "claimguard.cli",
            "examples/conversations/claim-amount-dispute.json",
        ]
        result = subprocess.run(
            command,
            check=False,
            cwd=Path(__file__).resolve().parents[1],
            env={"PYTHONPATH": "src"},
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["conversation_id"], "claim-amount-dispute-001")
        self.assertEqual(payload["score"], 70)
        self.assertEqual(payload["findings"][0]["rule_id"], "SEM-002")


if __name__ == "__main__":
    unittest.main()
