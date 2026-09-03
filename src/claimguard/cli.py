from __future__ import annotations

import argparse
import json
import sys

from claimguard.conversation import load_conversation
from claimguard.embeddings import DashScopeEmbeddingClient, EmbeddingError
from claimguard.knowledge import (
    KnowledgeError,
    build_knowledge_index,
    load_knowledge_index,
    parse_policy_markdown,
    save_knowledge_index,
)
from claimguard.qa import generate_qa_report
from claimguard.rules import load_rule_catalog


class _LazyDashScopeEmbeddingClient:
    def __init__(self):
        self._client = None

    def embed(self, texts):
        if self._client is None:
            self._client = DashScopeEmbeddingClient()
        return self._client.embed(texts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run ClaimGuard AI QA on a conversation fixture."
    )
    parser.add_argument("target", help="Conversation JSON fixture path or 'index'.")
    parser.add_argument("policy", nargs="?", help="Path to a policy Markdown file.")
    parser.add_argument("--output", help="Path for a generated knowledge index.")
    parser.add_argument("--index", help="Path to a knowledge index JSON file.")
    args = parser.parse_args(argv)

    try:
        if args.target == "index":
            if args.policy is None:
                parser.error("index requires a policy Markdown file")
            if args.output is None:
                parser.error("index requires --output")
            if args.index is not None:
                parser.error("--index is only supported for conversation QA")

            clauses = parse_policy_markdown(args.policy)
            knowledge_index = build_knowledge_index(clauses, DashScopeEmbeddingClient())
            save_knowledge_index(knowledge_index, args.output)
            return 0

        if args.policy is not None:
            parser.error("conversation QA accepts one positional conversation path")
        if args.output is not None:
            parser.error("--output is only supported with index")

        conversation = load_conversation(args.target)
        if args.index is None:
            report = generate_qa_report(conversation, load_rule_catalog())
        else:
            report = generate_qa_report(
                conversation,
                load_rule_catalog(),
                knowledge_index=load_knowledge_index(args.index),
                embedding_client=_LazyDashScopeEmbeddingClient(),
            )
        print(json.dumps(report.to_dict(), indent=2))
        return 0
    except (KnowledgeError, EmbeddingError, OSError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    except (KeyError, TypeError):
        print("Invalid conversation fixture", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
