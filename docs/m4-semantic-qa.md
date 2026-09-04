# M4: v0.4 Semantic QA

`v0.4.0` adds an opt-in semantic quality-inspection path for completed Chinese
text customer-service conversations. The existing deterministic CLI and
optional RAG grounding remain available without a semantic model call.

## Active Semantic Rules

The Qwen judge evaluates these four rules in one structured request:

| Rule | What it checks |
| --- | --- |
| `SEM-002` | Whether the agent addresses the customer's core question |
| `SEM-003` | Whether the agent is dismissive or impatient |
| `SEM-004` | Whether a complaint is acknowledged and soothed |
| `SEM-005` | Whether the agent makes an unsupported definite commitment |

The default semantic model is Alibaba Cloud Model Studio Qwen
`qwen3.7-plus`. The request uses `temperature: 0`, disables thinking, and
requires strict JSON Schema output. `CLAIMGUARD_SEMANTIC_MODEL` can override
the model in local ignored configuration when an operator has a compatible
deployment.

## Operator Command

Copy `.env.example` to the Git-ignored `.env` file and configure a local Model
Studio key. Then run:

```bash
PYTHONPATH=src python3 -m claimguard.cli examples/conversations/zh-semantic-qa.json --llm
```

`--llm` is an explicit paid network call. It reads the ignored local `.env`
file through the project configuration fallback; explicit process environment
variables take priority. Do not place a key in the command line, fixture,
documentation example, or Git history.

Without `--llm`, the CLI constructs no semantic client and makes no semantic
network request. The flag is valid only for conversation QA, not for the
`index` command.

## Evidence and Failure Contract

The semantic judge must return one decision for each active semantic rule. A
violation becomes a QA finding only if its evidence equals one complete agent
message from the reviewed transcript. The report builder rejects fabricated,
partial, customer-message, duplicate, malformed, or unsupported findings.

When a network, provider, or response-contract failure occurs, the CLI exits
with a concise error and emits no unvalidated semantic findings. Automated
tests use injected local responses and never call Model Studio.

## Deliberate Limits

This milestone does not add a Citation Judge, reranking, Copilot reply
generation, persistence, or web/API endpoints. RAG retrieval evidence remains
useful context for supported policy rules, but it is not citation-accuracy
judgment. All committed policy and conversation examples are synthetic.
