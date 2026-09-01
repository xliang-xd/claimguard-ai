from __future__ import annotations

import argparse
import json

from claimguard.conversation import load_conversation
from claimguard.qa import generate_qa_report
from claimguard.rules import load_rule_catalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run ClaimGuard AI QA on a conversation fixture."
    )
    parser.add_argument("conversation", help="Path to a conversation JSON fixture.")
    args = parser.parse_args(argv)

    conversation = load_conversation(args.conversation)
    report = generate_qa_report(conversation, load_rule_catalog())
    print(json.dumps(report.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
