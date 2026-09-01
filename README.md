# ClaimGuard AI

Insurance text customer service Copilot and AI quality assurance system.

ClaimGuard AI is a focused GitHub demo project for text-based insurance service. It does not handle calls, ASR, speaker diarization, OCR, video, or outbound dialing. V1 concentrates on two inputs:

1. A customer message currently being handled by an online service agent.
2. A completed text conversation that needs quality inspection.

## Architecture

![ClaimGuard AI architecture](docs/assets/architecture.svg)

The current core is the deterministic rule runner introduced in `v0.2.0`. Future milestones will add RAG grounding, LLM judges, and a web UI without changing the QA report contract.

## V1 Product

### Customer Service Copilot

The Copilot workflow helps an agent answer a customer during an active chat.

- Detect customer intent, such as claim amount dispute, denial explanation, policy clause lookup, or complaint.
- Retrieve relevant insurance knowledge.
- Draft a clear, compliant, clause-grounded reply.
- Warn the agent about risky phrases, unsupported commitments, and impatient wording.

### Quality Assurance

The QA workflow reviews completed conversations.

- Produce a quality score.
- Run semantic, process, and knowledge-grounded rules.
- Show violated rule IDs, risk levels, evidence, and reasoning.
- Suggest a better reply grounded in the correct policy clause.

## V1 Rule Matrix

| Rule ID | Rule | Category | Risk | Detection |
| --- | --- | --- | --- | --- |
| SEM-001 | Counter-questioning the customer | Semantic | Critical | LLM judge |
| SEM-002 | Answer does not address customer intent | Semantic | Critical | Intent + LLM judge |
| SEM-003 | Impatient service tone | Semantic | Critical | LLM judge |
| SEM-004 | Complaint not acknowledged or soothed | Semantic | Critical | Intent + LLM judge |
| SEM-005 | Unapproved commitment | Semantic | Critical | LLM judge |
| PROC-001 | Incomplete identity disclosure | Process | High | Rule + LLM |
| PROC-002 | Missing closing statement | Process | Low | Rule + LLM |
| RAG-001 | Claim amount dispute: deductible | Knowledge-grounded | Medium | RAG + LLM judge |
| RAG-002 | Pre-policy or waiting-period treatment denial | Knowledge-grounded | Medium | RAG + LLM judge |
| RAG-003 | Disease outside policy coverage | Knowledge-grounded | Medium | RAG + LLM judge |
| RAG-004 | Accident definition explanation | Knowledge-grounded | Medium | RAG + LLM judge |
| RAG-005 | Dynamic clause citation for pet insurance denial | Knowledge-grounded | High | Intent + RAG + Citation judge |

`RAG-005` is the V1 hero case because it demonstrates intent routing, retrieval, citation accuracy, and grounded answer quality in one scenario.

## Technical Direction

V1 should stay small and explicit:

```text
Router
  -> Knowledge workflow: RAG, citation grounding, answer drafting
  -> QA workflow: rule selection, judgment, evidence, scoring
```

The project should show product judgment, not agent sprawl. A compact workflow is easier to explain, test, and extend than a large multi-agent graph.

## Current Milestone

Current package version: `0.2.2`.

M2 adds the first deterministic rule runner. QA findings now come from conversation text instead of the fixture's `expected_risks` field. The fixture field remains as test oracle data while LLM and RAG behavior are still under development.

`v0.2.1` is a documentation patch that adds README architecture and roadmap diagrams.

`v0.2.2` is a documentation patch that records the maintained agent
orchestration and domestic model defaults in `docs/agent-orchestration.md`.

## Repository Layout

```text
docs/                       product scope and architecture notes
data/knowledge/             synthetic policy fixtures
examples/conversations/     demo conversation fixtures
src/claimguard/             Python package
tests/                      automated tests
```

## Versioning

Release tags use `vX.Y.Z`.

- Small fixes use `v0.0.Z` style patch bumps.
- Larger feature milestones use `v0.Y.0` minor bumps.
- Major `vX.0.0` releases are reserved for genuinely deliverable demo milestones.

See `docs/versioning.md` for the project policy.

## Quick Start

Run the current QA CLI demo:

```bash
PYTHONPATH=src python3 -m claimguard.cli examples/conversations/claim-amount-dispute.json
```

The command returns a JSON QA report with:

- `conversation_id`: reviewed conversation fixture ID.
- `scenario`: demo case description.
- `score`: deterministic quality score.
- `findings`: rule findings with rule ID, category, risk level, evidence, and recommendation.

Run the test suite:

```bash
python3 -m unittest discover -s tests
```

Load the V1 rule catalog:

```python
from claimguard.rules import load_rule_catalog

catalog = load_rule_catalog()
print(catalog.get("RAG-005").name)
```

## Roadmap

![ClaimGuard AI roadmap](docs/assets/roadmap.svg)

The roadmap keeps small documentation or fixture updates in patch releases, while capability milestones move the minor version forward.
