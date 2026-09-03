# Agent Orchestration

ClaimGuard AI uses a compact agent architecture for insurance text customer
service. The project should demonstrate reliable workflow design, grounded
judgment, and clear QA evidence instead of a large multi-agent chat graph.

## Current State

The current `v0.3.0` codebase keeps its deterministic QA workflow and adds two
separate RAG operations for supported Chinese policy scenarios:

```text
Index construction (explicit `claimguard index` command)
  -> Policy Parser -> Qwen Embedding -> Local Knowledge Index

Grounded QA (only with `--index`)
  -> Conversation Loader -> Rule Catalog -> Deterministic Rule Runner
  -> Query Embedding -> Existing Local Knowledge Index -> Retrieval Evidence
  -> QA Report Builder
```

This stage proves the basic quality-inspection contract: completed
conversation in, structured QA report out. Index construction is not part of
normal QA execution. When `--index` is supplied, matched Chinese RAG findings
include retrieved-clause evidence. The legacy invocation remains available
without an index or a model call.

## Future Target Topology

The target system exposes two product agents:

- `QA Agent`: reviews completed conversations after the service interaction.
- `Copilot Agent`: assists a service representative during an active chat.

Shared capabilities such as intent routing, retrieval, reranking, citation
checking, and report building stay as workflow nodes or tools. They are not
separate product-facing agents.

![ClaimGuard AI agent orchestration](assets/agent-orchestration.svg)

## Product Agents

The product-agent descriptions below are future topology. v0.3 implements the
deterministic CLI workflow above, not LLM-backed QA or Copilot agents.

### ClaimGuard Orchestrator

The orchestrator owns product-level routing and final response shape. It
selects the correct business workflow based on the input type:

- A completed text conversation goes to `QA Agent`.
- An active customer message goes to `Copilot Agent`.

The orchestrator keeps the report and suggestion contracts stable for CLI,
API, and future web UI entry points.

### QA Agent

The QA Agent handles after-call text quality inspection.

Input:

```text
completed conversation
rule catalog
optional policy knowledge
```

Output:

```text
score
findings
violated_rules
risk_level
evidence
reasoning
recommendation
retrieved_clause
citation_accuracy
```

Internal nodes:

- `Intent Router`: identifies the customer's core issue, such as claim amount
  dispute, denial explanation, complaint, or policy lookup.
- `Rule Selector`: chooses the relevant semantic, process, and
  knowledge-grounded rules for the scenario.
- `Knowledge Retriever`: retrieves policy clauses for RAG-backed rules.
- `Reranker`: reranks candidate clauses before judgment.
- `QA Judge`: evaluates semantic service quality, relevance, attitude, and
  process compliance.
- `Citation Judge`: checks whether the service answer uses the correct clause
  and explains it accurately.
- `Report Builder`: assembles the final QA report.

### Copilot Agent

The Copilot Agent handles live service assistance.

Input:

```text
current customer message
conversation context
policy knowledge
```

Output:

```text
customer_intent
recommended_clause
suggested_reply
risk_warnings
phrases_to_avoid
citation_check
```

Internal nodes:

- `Intent Router`: identifies what the customer is asking now.
- `Knowledge Retriever`: finds relevant policy clauses.
- `Reranker`: ranks retrieved clauses for the current intent.
- `Risk Guard`: detects risky wording, unsupported commitments, and missing
  appeasement.
- `Reply Writer`: drafts a clear, compliant, clause-grounded response.
- `Citation Checker`: verifies that the suggested reply is grounded in the
  retrieved clause.

## Domestic Model Defaults

For cost and compliance-sensitive insurance service scenarios, ClaimGuard AI
defaults to a China-local model stack.

| Component | Default Model | Purpose |
| --- | --- | --- |
| Intent Router | `qwen3.8-flash` | Low-cost routing and classification |
| Rule Selector | `qwen3.8-flash` | Fast rule selection and scenario narrowing |
| QA Judge | `qwen3.7-plus` | Semantic QA judgment and structured reasoning |
| Citation Judge | `qwen3.7-plus` | Clause accuracy and completeness checks |
| Risk Guard | `qwen3.7-plus` | Compliance-sensitive risk detection |
| Reply Writer | `qwen3.7-plus` | Copilot response generation |
| Hard Case Judge | `qwen3.8-max` | Complex demo cases and difficult disputes |
| Embedding | `qwen3.7-text-embedding` | v0.3 dense retrieval for policy clauses |
| Reranking | `qwen3-rerank` | Deferred; not used by the v0.3 runtime |

The default provider is Alibaba Cloud Model Studio / Qwen. The default region
should be a mainland China region, such as `cn-beijing`, when API access is
configured.

References:

- Qwen model selection: <https://docs.qwencloud.com/developer-guides/getting-started/model-selection>
- Qwen embeddings: <https://docs.qwencloud.com/developer-guides/embeddings/embedding>
- Qwen reranking: <https://docs.qwencloud.com/developer-guides/embeddings/reranking>
- Qwen structured output: <https://docs.qwencloud.com/developer-guides/text-generation/structured-output>
- Alibaba Cloud Model Studio product notes: <https://help.aliyun.com/zh/model-studio/what-is-model-studio>

## Design Principles

- Keep the public architecture to two product agents.
- Keep specialized steps as tools or workflow nodes unless they need their own
  state, policy, or ownership boundary.
- Prefer structured JSON outputs for judgments and reports.
- Keep RAG evidence explicit: retrieved clause, clause ID, source document, and
  citation judgment should be visible in the final report.
- Treat v0.3 retrieval evidence as deterministic context, not an LLM citation
  judgment. Reranking and LLM citation checks are future work.
- Treat deterministic rules, LLM judges, RAG, and evaluation fixtures as
  separate layers so each can be tested independently.
- Use China-local providers by default for cost and compliance; document any
  provider change before implementation.

## Update Policy

Update this document and the orchestration diagram whenever any of these change:

- product-facing agent topology
- model provider or default model names
- embedding or reranking strategy
- QA report contract
- Copilot suggestion contract
- RAG evidence format
- compliance assumptions about data locality or model usage
