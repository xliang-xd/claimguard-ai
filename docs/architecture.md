# Architecture

ClaimGuard AI uses three complementary judgment paths depending on the risk
type. In `v0.4.0`, deterministic rules always run; RAG grounding and semantic
judgment are opt-in additions to the same stable QA report.

## Semantic QA (Current)

For a completed conversation, `--llm` invokes one Alibaba Cloud Model Studio
Qwen `qwen3.7-plus` request with strict JSON Schema, `temperature: 0`, and
thinking disabled. It evaluates `SEM-002` through `SEM-005`: relevance,
impatient tone, complaint acknowledgement, and unsupported commitments.

The report builder accepts a semantic violation only when the returned evidence
is an exact, complete agent message from the transcript. It deduplicates any
rule already emitted by deterministic matching. Provider, transport, and
contract errors stop the command rather than adding unvalidated findings.

Without `--llm`, the semantic client is never created and the normal CLI makes
no semantic network request.

## Process QA (Future)

The target process rules will combine deterministic checks with LLM
normalization. This future work aims to accept flexible wording while still
enforcing required service steps, such as identity disclosure and conversation
closing.

## Knowledge-grounded QA (Current)

Knowledge-grounded rules parse supported Chinese policy headings, use
`qwen3.7-text-embedding` to build and query a local JSON index, and attach the
top retrieved clause to a finding. The implemented rules are `RAG-001` through
`RAG-005`; they cover deductible, waiting-period, coverage, accident, and
denial-citation cases. The report exposes clause ID, title, text, source path,
and retrieval score as additive evidence.

Index construction and query-time retrieval are deliberately separate:

```text
Explicit index command
  Policy Markdown -> Parser -> Qwen embedding -> ignored local JSON index

QA command with --index
  Matched RAG rule -> query embedding -> existing local index -> clause evidence
```

The local index is an ignored operator artifact under `.claimguard/`. The
embedding client is created only for index creation and grounded retrieval; the
legacy QA CLI remains fully offline and does not require a key.

## Deferred Work

`v0.4.0` does not implement Citation Judge, reranking, Copilot reply
generation, persistence, or web/API endpoints. Retrieval evidence identifies a
selected clause; it does not make a citation-accuracy judgment.

## Planned Directories

```text
data/knowledge/              policy text and clause fixtures
examples/conversations/      sample conversations for demos and tests
src/claimguard/              application package
tests/                       automated checks
```

See `docs/m3-rag-grounding.md` for v0.3 operating instructions and
`docs/m4-semantic-qa.md` for the v0.4 semantic operating contract.

See `docs/agent-orchestration.md` for the maintained agent topology, domestic
model defaults, and update policy.
