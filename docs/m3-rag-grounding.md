# M3: v0.3 RAG Grounding

`v0.3.0` adds deterministic, evidence-producing policy grounding to the QA
CLI. It is deliberately narrow: the runtime retrieves a clause only for a
matched Chinese knowledge rule and returns that clause as additive evidence.
The existing QA command remains compatible and offline when no index is used.

## Supported Chinese Policy Rules

| Rule | Supported situation | Expected policy clause |
| --- | --- | --- |
| `RAG-001` | Claim amount dispute involving a deductible | `12` 免赔额 |
| `RAG-002` | Treatment denied because of a waiting period | `18` 等待期 |
| `RAG-003` | Disease is outside the covered scope | `24` 疾病保障范围 |
| `RAG-004` | Customer asks for an accident definition | `31` 意外事故定义 |
| `RAG-005` | Pet-insurance denial needs a dynamic clause citation | retrieved matching clause |

The rule selection is deterministic phrase matching. Grounding evidence
contains the retrieved clause ID, title, full clause text, source path, and
retrieval score.

## Model and Local Index

The v0.3 embedding boundary defaults to Alibaba Cloud Model Studio / Qwen
`qwen3.7-text-embedding` with 1024 dimensions. It is used only while building
an index and while retrieving evidence for a grounded QA run. The index is a
validated JSON artifact and should be kept under the ignored `.claimguard/`
directory. It is not source data and must be rebuilt after a policy changes or
when the embedding model or dimensions change.

`qwen3-rerank` is documented as a future option but is not invoked in v0.3.
LLM judges and LLM citation judgment are also deferred.

## Operator Setup

Set `DASHSCOPE_API_KEY` in the operator's local process without committing or
printing it, then create an index from the committed synthetic policy fixture:

```bash
export DASHSCOPE_API_KEY=your-key
PYTHONPATH=src python3 -m claimguard.cli index data/knowledge/petcare-plus-policy-zh.md \
  --output .claimguard/petcare-plus-policy.json
```

Run grounded QA against that local artifact:

```bash
PYTHONPATH=src python3 -m claimguard.cli examples/conversations/zh-deductible-dispute.json \
  --index .claimguard/petcare-plus-policy.json
```

For a manual real-API release check, run the two commands above only when the
key is already configured in the current process. Inspect the command output
for a successful index and clause evidence, but do not print, log, or otherwise
expose the key. The legacy command requires neither an index nor a key:

```bash
PYTHONPATH=src python3 -m claimguard.cli examples/conversations/claim-amount-dispute.json
```

## Known Limits

- Coverage is limited to the five fixture-backed Chinese RAG cases above.
- Retrieval uses one embedding model and cosine similarity without reranking.
- Retrieval evidence shows the selected clause; it does not prove a generated
  answer is legally complete or perform an LLM citation judgment.
- The project uses synthetic policy and conversation fixtures, not production
  insurance records.
- Network access is required only for embedding index creation and grounded
  retrieval. Unit tests use local literal vectors and make no remote calls.
