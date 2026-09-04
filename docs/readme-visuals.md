# README Visuals

This document records the technical diagrams updated through `v0.4.0`.

## Assets

- `docs/assets/architecture.svg`: separate index construction and query-time QA paths, including deterministic rules, optional retrieval, opt-in Semantic QA, evidence validation, and deduplication.
- `docs/assets/architecture.png`: rendered preview used for visual review.
- `docs/assets/roadmap.svg`: versioned roadmap from `v0.1.0` through the planned portfolio demo, with `v0.4.0 Semantic QA` marked current.
- `docs/assets/roadmap.png`: rendered preview used for visual review.
- `docs/assets/agent-orchestration.svg`: implemented QA workflow plus deferred Copilot and advanced judgment capabilities, with domestic model defaults.
- `docs/assets/agent-orchestration.png`: rendered preview used for visual review.

## Current Progress Markers

- The architecture diagram marks `v0.4.0 Semantic QA` as the current capability and keeps index creation separate from query-time retrieval.
- The roadmap marks `v0.4.0 Semantic QA` as the current implementation stage; Citation Judge, reranking, Copilot, and API are future scope.
- The agent orchestration diagram marks opt-in Semantic QA as current, and shows the Copilot Agent only in the deferred lane.

## Validation

The diagrams were generated with the `fireworks-tech-graph` skill and validated with:

```bash
PYTHONPATH=/tmp/claimguard-cairosvg sh /Users/lxd/.codex/skills/fireworks-tech-graph/scripts/validate-svg.sh docs/assets/architecture.svg
PYTHONPATH=/tmp/claimguard-cairosvg sh /Users/lxd/.codex/skills/fireworks-tech-graph/scripts/validate-svg.sh docs/assets/roadmap.svg
PYTHONPATH=/tmp/claimguard-cairosvg sh /Users/lxd/.codex/skills/fireworks-tech-graph/scripts/validate-svg.sh docs/assets/agent-orchestration.svg
```

All SVG files passed XML, marker, collision, semantic geometry, composition, and render validation. The exported PNG files were visually inspected for cropping, text overlap, and readability.
