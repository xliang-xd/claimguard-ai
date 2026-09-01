# Architecture

ClaimGuard AI uses three judgment paths depending on the risk type.

## Semantic QA

Semantic rules use intent detection plus LLM judgment to inspect tone, relevance, complaint handling, and unsupported commitments. These rules are not simple keyword checks because hostile or evasive responses can appear in many forms.

## Process QA

Process rules combine deterministic checks with LLM normalization. The goal is to accept flexible wording while still enforcing required service steps, such as identity disclosure and conversation closing.

## Knowledge-grounded QA

Knowledge-grounded rules retrieve policy clauses and judge whether the agent's explanation is complete, correct, and properly cited. `RAG-005` is the V1 hero case because it demonstrates retrieval, citation accuracy, and answer quality in one flow.

## Planned Directories

```text
data/knowledge/              policy text and clause fixtures
examples/conversations/      sample conversations for demos and tests
src/claimguard/              application package
tests/                       automated checks
```

See `docs/agent-orchestration.md` for the maintained agent topology, domestic
model defaults, and update policy.
