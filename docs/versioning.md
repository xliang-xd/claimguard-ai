# Versioning Policy

ClaimGuard AI uses Git release tags in the form `vX.Y.Z`.

## Bump Rules

- `v0.0.Z`: small fixes, documentation corrections, fixture tweaks, and narrow internal improvements.
- `v0.Y.0`: larger feature milestones, new user-facing commands, new workflows, and meaningful capability upgrades.
- `vX.0.0`: deliverable major releases only, such as a polished demo that can be shared as a complete portfolio milestone.

## Current Interpretation

- M1 QA CLI is a feature milestone, so it fits the `v0.1.0` level.
- M2 deterministic rule runner is a larger capability upgrade, so it should move the project to `v0.2.0` when merged.
- Patch-only follow-ups after M2 should use `v0.2.1`, `v0.2.2`, and so on.

## Practical Rules

- Python package metadata uses PEP 440 versions without the leading `v`, such as `0.2.0`.
- Git tags and GitHub release names use the leading `v`, such as `v0.2.0`.
- Do not create a `v1.0.0` release until ClaimGuard has a usable end-to-end demo with documented setup, example data, tests, and a clear user workflow.

