# v0.6 Final Fix Report

## Status

All requested final-review fixes are implemented in the current worktree.

## Fixes

1. `QwenReranker` now rejects a configured model whose normalized name does not begin with `qwen`. Existing Qwen-family naming compatibility and the established configurable compatible base URL remain unchanged.
2. Successful `run_completed` audit events now retain `current_agent` and `evidence_count`, alongside the existing citation verdict status and citation IDs. They do not include draft text, evidence content, or verdict reason codes.
3. The CLI assembly test now patches the real imported `QwenCitationJudge` binding without `create=True`.
4. The four Chinese synthetic citation cases now run through a deterministic local verdict layer and assert their expected status and citations without network access.

## Validation

- Focused offline tests: 19 passed.
- Full offline suite: 192 passed.
- `git diff --check`: passed.

## Concerns

No unresolved concerns. The full suite ran with the worktree's existing virtual environment; no network calls or dependency installs were required.
