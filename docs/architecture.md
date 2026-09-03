# Architecture

ClaimGuard AI uses three judgment paths depending on the risk type. In v0.3,
the deterministic knowledge-grounded path is implemented for five Chinese
policy scenarios and attaches retrieved-clause evidence to its findings.

## Semantic QA

Semantic rules use intent detection plus LLM judgment to inspect tone, relevance, complaint handling, and unsupported commitments. These rules are not simple keyword checks because hostile or evasive responses can appear in many forms.

## Process QA

Process rules combine deterministic checks with LLM normalization. The goal is to accept flexible wording while still enforcing required service steps, such as identity disclosure and conversation closing.

## Knowledge-grounded QA

Knowledge-grounded rules parse supported Chinese policy headings, use
`qwen3.7-text-embedding` to build and query a local JSON index, and attach the
top retrieved clause to a finding. The implemented v0.3 rules are `RAG-001`
through `RAG-005`; they cover deductible, waiting-period, coverage, accident,
and denial-citation cases. The report exposes clause ID, title, text, source
path, and retrieval score as additive evidence. `RAG-005` remains the V1 hero
case because it demonstrates retrieval and citation evidence in one flow.

The local index is an ignored operator artifact under `.claimguard/`. The
embedding client is created only for index creation and grounded retrieval;
the legacy QA CLI remains fully offline and does not require a key.

## Planned Directories

```text
data/knowledge/              policy text and clause fixtures
examples/conversations/      sample conversations for demos and tests
src/claimguard/              application package
tests/                       automated checks
```

See `docs/m3-rag-grounding.md` for v0.3 operating instructions and known
limitations. Reranking and LLM citation judgment are intentionally deferred.

See `docs/agent-orchestration.md` for the maintained agent topology, domestic
model defaults, and update policy.
