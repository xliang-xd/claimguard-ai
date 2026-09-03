# README Visuals

This document records the technical diagrams updated through `v0.3.0`.

## Assets

- `docs/assets/architecture.svg`: v0.3 architecture, including the policy parser, Qwen embedding client, ignored local index, retrieval evidence, deterministic QA, and future LLM judges.
- `docs/assets/architecture.png`: rendered preview used for visual review.
- `docs/assets/roadmap.svg`: versioned roadmap from `v0.1.0` through the planned portfolio demo.
- `docs/assets/roadmap.png`: rendered preview used for visual review.
- `docs/assets/agent-orchestration.svg`: maintained agent topology with two product agents, v0.3 retrieval evidence, the local index lifecycle, and domestic model defaults.
- `docs/assets/agent-orchestration.png`: rendered preview used for visual review.

## Current Progress Markers

- The architecture diagram marks `v0.3.0 deterministic RAG grounding` as the current capability.
- The roadmap marks `v0.2.0 Rule Runner` as the current implementation stage.
- `v0.2.1 Visual Docs` is shown as a patch release, not a capability milestone.
- The agent orchestration diagram marks `v0.3.0 grounded QA evidence` as the current state and labels `qwen3.7-text-embedding` as active; reranking remains deferred.

## Validation

The diagrams were generated with the `fireworks-tech-graph` skill and validated with:

```bash
PYTHONPATH=/tmp/claimguard-cairosvg sh /Users/lxd/.codex/skills/fireworks-tech-graph/scripts/validate-svg.sh docs/assets/architecture.svg
PYTHONPATH=/tmp/claimguard-cairosvg sh /Users/lxd/.codex/skills/fireworks-tech-graph/scripts/validate-svg.sh docs/assets/roadmap.svg
PYTHONPATH=/tmp/claimguard-cairosvg sh /Users/lxd/.codex/skills/fireworks-tech-graph/scripts/validate-svg.sh docs/assets/agent-orchestration.svg
```

All SVG files passed XML, marker, collision, semantic geometry, composition, and render validation. The exported PNG files were visually inspected for cropping, text overlap, and readability.
