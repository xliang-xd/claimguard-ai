# ClaimGuard AI V1 Scope

ClaimGuard AI focuses on text-based insurance customer service. It intentionally excludes phone calls, ASR, speaker diarization, OCR, video, outbound calls, and audio quality inspection.

## Product Surface

V1 has two core workflows:

1. Customer Service Copilot
   - Reads an in-progress customer message.
   - Detects customer intent.
   - Retrieves relevant policy knowledge.
   - Suggests a grounded reply.
   - Highlights risky wording the agent should avoid.

2. Quality Assurance
   - Reads a completed text conversation.
   - Scores service quality.
   - Runs semantic, process, and knowledge-grounded checks.
   - Shows evidence, violated rule IDs, cited clauses, and improved replies.

## Technical Shape

The first implementation should stay workflow-oriented:

```text
Router
  -> Knowledge workflow: intent, retrieval, citation grounding
  -> QA workflow: rule selection, judgment, evidence, scoring
```

V1 does not need many agents. The business tasks are structured enough that a small workflow graph is clearer and easier to test than an oversized multi-agent setup.

