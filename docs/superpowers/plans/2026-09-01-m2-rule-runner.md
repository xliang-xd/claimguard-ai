# M2 Rule Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace fixture-driven QA findings with a deterministic local rule runner for the first demo risks.

**Architecture:** M2 adds a small rule runner that inspects conversation text and returns matched rule IDs with evidence. `generate_qa_report` will consume runner matches instead of `conversation.expected_risks`, while `expected_risks` remains in fixtures as test oracle data. The runner is intentionally simple and deterministic so it can later be replaced or supplemented by LLM/RAG judges without changing the CLI report contract.

**Tech Stack:** Python 3.9+, standard library only, `unittest`, JSON fixtures.

**Spec:** `docs/v1-scope.md`, `docs/architecture.md`, and `docs/m1-qa-cli.md`

## Global Constraints

- Every important change must be committed and pushed to GitHub.
- Every feature milestone must update documentation before it is considered complete.
- Tests must pass before each feature commit is pushed.
- M2 must not introduce external runtime dependencies.
- M2 changes the project version to `0.2.0`, with release/tag naming documented as `v0.2.0`.
- Keep `expected_risks` in fixtures as expected test data, not as QA report input.

---

## File Structure

- `src/claimguard/rule_runner.py`: Deterministic rule matching over text conversations.
- `src/claimguard/qa.py`: Generate reports from rule runner matches.
- `src/claimguard/__init__.py`: Export package version and public interfaces.
- `pyproject.toml`: Bump package version to `0.2.0`.
- `tests/test_rule_runner.py`: Rule runner behavior for the current demo fixture.
- `tests/test_qa_report.py`: Report generation proves findings do not depend on fixture `expected_risks`.
- `tests/test_cli.py`: CLI still returns the M1-compatible JSON shape.
- `README.md`: Describe M2 deterministic rule runner.
- `docs/m2-rule-runner.md`: Milestone record for M2.

## Task 1: Deterministic Rule Runner

**Files:**
- Create: `src/claimguard/rule_runner.py`
- Test: `tests/test_rule_runner.py`

**Interfaces:**
- Consumes: `Conversation` from `load_conversation`.
- Produces: `run_rules(conversation: Conversation) -> list[RuleMatch]`.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.conversation import load_conversation
from claimguard.rule_runner import run_rules


class RuleRunnerTest(unittest.TestCase):
    def test_matches_demo_risks_from_conversation_text(self):
        conversation = load_conversation(Path("examples/conversations/claim-amount-dispute.json"))

        matches = run_rules(conversation)

        self.assertEqual([match.rule_id for match in matches], ["SEM-002", "SEM-003", "RAG-001"])
        self.assertIn("final result", matches[0].evidence.lower())
        self.assertIn("only reimburse", matches[2].evidence.lower())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_rule_runner.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'claimguard.rule_runner'`.

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from dataclasses import dataclass

from claimguard.conversation import Conversation


@dataclass(frozen=True)
class RuleMatch:
    rule_id: str
    evidence: str


def run_rules(conversation: Conversation) -> list[RuleMatch]:
    matches: list[RuleMatch] = []
    customer_text = _joined_text(conversation, "customer")
    agent_text = _joined_text(conversation, "agent")

    if _has_claim_amount_dispute(customer_text) and _has_evasive_claim_answer(agent_text):
        matches.append(RuleMatch("SEM-002", _first_agent_message(conversation)))

    if _has_impatient_tone(agent_text):
        matches.append(RuleMatch("SEM-003", _first_agent_message(conversation)))

    if _has_claim_amount_dispute(customer_text) and not _mentions_deductible_or_clause(agent_text):
        matches.append(RuleMatch("RAG-001", _first_customer_message(conversation)))

    return matches


def _joined_text(conversation: Conversation, role: str) -> str:
    return " ".join(message.content for message in conversation.messages if message.role == role).lower()


def _first_agent_message(conversation: Conversation) -> str:
    for message in conversation.messages:
        if message.role == "agent":
            return message.content
    return ""


def _first_customer_message(conversation: Conversation) -> str:
    for message in conversation.messages:
        if message.role == "customer":
            return message.content
    return ""


def _has_claim_amount_dispute(text: str) -> bool:
    return ("reimburse" in text or "claim" in text or "payout" in text) and ("why" in text or "only" in text)


def _has_evasive_claim_answer(text: str) -> bool:
    return "review team" in text or "final result" in text or "do not know" in text


def _has_impatient_tone(text: str) -> bool:
    return "final result" in text or "just like this" in text


def _mentions_deductible_or_clause(text: str) -> bool:
    return "deductible" in text or "clause" in text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_rule_runner.py`
Expected: PASS.

- [ ] **Step 5: Commit and push**

```bash
git add src/claimguard/rule_runner.py tests/test_rule_runner.py
git commit -m "feat: add deterministic rule runner"
git push
```

## Task 2: QA Reports Use Rule Runner

**Files:**
- Modify: `src/claimguard/qa.py`
- Modify: `tests/test_qa_report.py`

**Interfaces:**
- Consumes: `run_rules(conversation) -> list[RuleMatch]`.
- Produces: `generate_qa_report(conversation: Conversation, catalog: RuleCatalog) -> QAReport`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_qa_report.py`:

```python
    def test_report_findings_do_not_depend_on_expected_risks_fixture_field(self):
        conversation = load_conversation(Path("examples/conversations/claim-amount-dispute.json"))
        conversation_without_expected = type(conversation)(
            id=conversation.id,
            scenario=conversation.scenario,
            messages=conversation.messages,
            expected_risks=[],
        )

        report = generate_qa_report(conversation_without_expected, load_rule_catalog())

        self.assertEqual([finding.rule_id for finding in report.findings], ["SEM-002", "SEM-003", "RAG-001"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_qa_report.py`
Expected: FAIL because report generation currently loops over `conversation.expected_risks`.

- [ ] **Step 3: Write minimal implementation**

Update `generate_qa_report` to call `run_rules(conversation)`. Use each `RuleMatch.evidence` for the corresponding finding.

```python
from claimguard.rule_runner import run_rules


def generate_qa_report(conversation: Conversation, catalog: RuleCatalog) -> QAReport:
    findings = []
    for match in run_rules(conversation):
        rule = catalog.get(match.rule_id)
        findings.append(
            Finding(
                rule_id=rule.id,
                rule_name=rule.name,
                category=rule.category,
                risk_level=rule.risk_level,
                evidence=match.evidence,
                recommendation=(
                    "Replace the response with a clear, empathetic, "
                    f"policy-grounded explanation for {rule.id}."
                ),
            )
        )

    return QAReport(
        conversation_id=conversation.id,
        scenario=conversation.scenario,
        score=max(0, 100 - (10 * len(findings))),
        findings=findings,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_qa_report.py`
Expected: PASS.

- [ ] **Step 5: Commit and push**

```bash
git add src/claimguard/qa.py tests/test_qa_report.py
git commit -m "feat: generate QA reports from rule runner"
git push
```

## Task 3: Version and Documentation

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/claimguard/__init__.py`
- Create: `docs/m2-rule-runner.md`
- Modify: `README.md`

**Interfaces:**
- Produces: package version `0.2.0` and documented release tag target `v0.2.0`.

- [ ] **Step 1: Update version metadata**

Update `pyproject.toml`:

```toml
version = "0.2.0"
```

Update `src/claimguard/__init__.py`:

```python
__version__ = "0.2.0"
```

- [ ] **Step 2: Update docs**

Add `docs/m2-rule-runner.md`:

```markdown
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
```

Update README to mention that QA findings now come from the deterministic rule runner rather than the fixture's `expected_risks`.

- [ ] **Step 3: Run all tests**

Run: `python3 -m unittest discover -s tests`
Expected: all tests pass.

- [ ] **Step 4: Commit and push**

```bash
git add pyproject.toml src/claimguard/__init__.py README.md docs/m2-rule-runner.md docs/superpowers/plans/2026-09-01-m2-rule-runner.md
git commit -m "docs: record M2 rule runner milestone"
git push
```

## Final Verification

- [ ] Run `python3 -m unittest discover -s tests`.
- [ ] Run `PYTHONPATH=src python3 -m claimguard.cli examples/conversations/claim-amount-dispute.json`.
- [ ] Confirm report findings are `SEM-002`, `SEM-003`, and `RAG-001`.
- [ ] Confirm `pyproject.toml` contains `version = "0.2.0"`.
- [ ] Confirm `git status --short` is clean.
- [ ] Merge `codex/m2-rule-runner` into `main`.
- [ ] Push `main` to GitHub.
- [ ] Create and push Git tag `v0.2.0`.
