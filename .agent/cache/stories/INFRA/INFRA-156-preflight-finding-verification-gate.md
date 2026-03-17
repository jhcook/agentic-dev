# INFRA-156: Preflight Finding Verification Gate

## State

COMMITTED

## Problem Statement

The `agent preflight` governance panel produces AI-generated findings with high false-positive rates (observed 33–67% hallucination across recent runs). Findings like "missing trailing newline" or "CHANGELOG not updated" are reported even when the code is demonstrably correct. This erodes developer trust and wastes time manually triaging AI noise vs. real issues.

This story introduces a hybrid verification gate that runs **after** the AI panel generates findings, applying deterministic checks where possible and LLM self-review as a fallback, to confirm or dismiss each finding before presenting it to the developer.

## User Story

As a **Platform Developer**, I want **preflight findings to be verified before they are reported** so that **I only see actionable, evidence-backed issues and can trust the governance output.**

## Acceptance Criteria

- [ ] **AC-1**: A new `FindingVerifier` class is introduced in `agent.core.check` that accepts a list of raw AI findings and returns only verified findings.
- [ ] **AC-2**: Deterministic verifiers are implemented for the following common finding types:
  - Missing return type hints → AST-parse the referenced function and check for a return annotation.
  - Missing trailing newline → Check if the file's last byte is `\n`.
  - Missing license header → Check if the first N lines contain the Apache 2.0 header pattern.
  - CHANGELOG not updated → Check if `CHANGELOG.md` is in the staged diff (`git diff --cached --name-only`).
  - Missing docstrings → AST-parse the referenced function/class and check for a docstring node.
- [ ] **AC-3**: For findings that cannot be deterministically verified, an LLM self-review pass is invoked: the finding + referenced file content are sent to the LLM with a prompt asking for evidence. Findings without evidence are demoted to warnings or dropped.
- [ ] **AC-4**: The preflight summary table includes a new `Verified` column showing how many findings passed verification vs. were dismissed.
- [ ] **AC-5**: Dismissed findings are logged at DEBUG level with the reason for dismissal (e.g., "file ends with newline", "CHANGELOG is staged").
- [ ] **Negative Test**: A finding referencing a non-existent file is automatically dismissed with an appropriate log message.

## Non-Functional Requirements

- Performance: Deterministic checks must complete in < 100ms per finding. LLM self-review adds at most one additional API call per unverifiable finding.
- Observability: Verification pass emits structured log events with `finding_id`, `verification_method` (deterministic|llm), and `result` (confirmed|dismissed).
- Security: No PII or file contents are logged at INFO level or above during verification.

## Linked ADRs

- (none yet — may warrant an ADR if the verification architecture becomes complex)

## Linked Journeys

- (none — internal infrastructure improvement)

## Impact Analysis Summary

Components touched: `agent.core.check` (MODIFIED — new verifier module), preflight reporting (MODIFIED — add Verified column).
Workflows affected: `agent preflight` output and finding accuracy.
Risks identified: LLM self-review fallback could itself hallucinate — bounded by requiring quoted evidence from the file.

## Test Strategy

- Unit tests for each deterministic verifier (type hints, newlines, license, CHANGELOG, docstrings).
- Unit test for the LLM fallback path (mock the AI response).
- Integration test: run preflight on a known-good commit and assert zero false positives for deterministic categories.
- Negative test: finding referencing non-existent file is dismissed.

## Rollback Plan

Remove the `FindingVerifier` and revert to unverified findings — the preflight pipeline output returns to its current behaviour.

## Copyright

Copyright 2026 Justin Cook
