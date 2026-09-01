# M1 QA CLI

M1 introduces the first local QA loop for ClaimGuard AI.

## What Works

- Load a completed text conversation fixture.
- Load the V1 rule catalog.
- Generate a deterministic QA report.
- Return JSON with conversation ID, scenario, score, findings, evidence, and recommendations.

## Intentional Limits

- No live LLM judge yet.
- No vector search or real RAG yet.
- Findings come from fixture `expected_risks` so the report contract can stabilize before model behavior is added.

## Run

```bash
PYTHONPATH=src python3 -m claimguard.cli examples/conversations/claim-amount-dispute.json
```

## Report Fields

- `conversation_id`: fixture identifier for the reviewed conversation.
- `scenario`: human-readable case description.
- `score`: deterministic quality score, currently `100 - 10 * finding_count`.
- `findings`: ordered list of rule findings generated from the fixture's expected risks.
- `evidence`: first agent response used as a deterministic evidence snippet in M1.
- `recommendation`: placeholder coaching text that future LLM/RAG work will replace with clause-grounded suggestions.

