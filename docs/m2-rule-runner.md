# M2 Rule Runner

M2 replaces fixture-driven QA findings with the first deterministic local rule runner.

## What Works

- Detect `SEM-002` when a claim amount dispute receives an evasive answer.
- Detect `SEM-003` when an agent response uses impatient or final-result wording.
- Detect `RAG-001` when a claim amount dispute lacks deductible or clause explanation.
- Keep the CLI report JSON shape from M1.

## Intentional Limits

- The runner is rule-based and English-fixture oriented.
- It covers the demo path before expanding to all 12 V1 rules.
- RAG and LLM judges are still future milestones.

## Version

M2 is a minor feature milestone and maps to package version `0.2.0` and release tag `v0.2.0`.

