# README Visuals

This document records the technical diagrams added in `v0.2.1` and `v0.2.2`.

## Assets

- `docs/assets/architecture.svg`: full project architecture, including current deterministic QA, future UI/API, RAG grounding, LLM judges, tests, reports, docs, and GitHub versioning.
- `docs/assets/architecture.png`: rendered preview used for visual review.
- `docs/assets/roadmap.svg`: versioned roadmap from `v0.1.0` through the planned portfolio demo.
- `docs/assets/roadmap.png`: rendered preview used for visual review.
- `docs/assets/agent-orchestration.svg`: maintained agent topology with two product agents, shared workflow nodes, and domestic model defaults.
- `docs/assets/agent-orchestration.png`: rendered preview used for visual review.

## Current Progress Markers

- The architecture diagram marks the current core as `v0.2.0 deterministic rules`.
- The roadmap marks `v0.2.0 Rule Runner` as the current implementation stage.
- `v0.2.1 Visual Docs` is shown as a patch release, not a capability milestone.
- The agent orchestration diagram marks `v0.2.2 docs + deterministic QA` as the current state.

## Validation

The diagrams were generated with the `fireworks-tech-graph` skill and validated with:

```bash
PYTHONPATH=/tmp/claimguard-cairosvg sh /Users/lxd/.codex/skills/fireworks-tech-graph/scripts/validate-svg.sh docs/assets/architecture.svg
PYTHONPATH=/tmp/claimguard-cairosvg sh /Users/lxd/.codex/skills/fireworks-tech-graph/scripts/validate-svg.sh docs/assets/roadmap.svg
PYTHONPATH=/tmp/claimguard-cairosvg sh /Users/lxd/.codex/skills/fireworks-tech-graph/scripts/validate-svg.sh docs/assets/agent-orchestration.svg
```

All SVG files passed XML, marker, collision, semantic geometry, composition, and render validation. The exported PNG files were visually inspected for cropping, text overlap, and readability.
