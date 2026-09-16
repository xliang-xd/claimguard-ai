from __future__ import annotations

import argparse
import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import asdict
import json
from pathlib import Path
import sys

from claimguard.agent_runtime.agents import build_copilot_agents
from claimguard.agent_runtime.audit import JsonlAuditSink
from claimguard.agent_runtime.evidence import EvidenceLedger
from claimguard.agent_runtime.policy_tool import build_search_policy_tool
from claimguard.agent_runtime.provider import AgentProviderError, QwenModelProvider, build_run_config
from claimguard.agent_runtime.runtime import CopilotRuntime, CopilotTurnResult
from claimguard.agent_runtime.settings import AgentSettingsError, load_agent_runtime_settings
from claimguard.agent_runtime.state import CopilotContext, InMemorySessionStore
from claimguard.embeddings import DashScopeEmbeddingClient, EmbeddingError
from claimguard.knowledge import KnowledgeError, load_knowledge_index
from claimguard.reranking import QwenReranker, RerankingError


TurnExecutor = Callable[[argparse.Namespace], Awaitable[CopilotTurnResult]]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the ClaimGuard AI customer service Copilot."
    )
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--index", required=True)
    parser.add_argument("--audit", default=".claimguard/audit.jsonl")
    parser.add_argument("message")
    return parser


async def execute_turn(args: argparse.Namespace) -> CopilotTurnResult:
    settings = load_agent_runtime_settings()
    provider = QwenModelProvider(settings)
    run_config = build_run_config(provider, settings.openai_tracing_enabled)
    context = CopilotContext(
        tenant_id=args.tenant_id,
        session_id=args.session_id,
        user_id=args.user_id,
        knowledge_index=load_knowledge_index(args.index),
        embedding_client=DashScopeEmbeddingClient(),
        audit_sink=JsonlAuditSink(Path(args.audit)),
        reranker=QwenReranker(),
        evidence_ledger=EvidenceLedger(),
    )
    agents = build_copilot_agents(settings, build_search_policy_tool())
    runtime = CopilotRuntime(
        agents=agents,
        run_config=run_config,
        session_store=InMemorySessionStore(),
    )
    return await runtime.run_turn(context, args.message)


def main(
    argv: list[str] | None = None,
    turn_executor: TurnExecutor = execute_turn,
) -> int:
    args = build_parser().parse_args(argv)
    if not Path(args.index).is_file():
        print("Knowledge index not found", file=sys.stderr)
        return 2
    try:
        result = asyncio.run(turn_executor(args))
    except (
        AgentSettingsError,
        AgentProviderError,
        EmbeddingError,
        KnowledgeError,
        RerankingError,
        OSError,
    ):
        print("Copilot request failed", file=sys.stderr)
        return 2
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
