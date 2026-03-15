# INFRA-134: Shift-Left Runbook Validation with Pydantic

## State

COMMITTED

## Problem Statement

Runbook validation currently relies on regex-based parsing in `parser.py` (`validate_runbook_schema`, lines 152-231). This approach catches structural violations (missing `<<<SEARCH` blocks, missing fences) but cannot enforce semantic constraints: hallucinated file paths, syntactically broken SEARCH blocks, or empty replacement content slip through. Malformed runbooks then fail during `agent implement`, wasting time and leaving the working tree in an inconsistent state.

## User Story

As a **developer**, I want **runbooks to be validated by strict Pydantic schemas before they are written to disk** so that **100% of runbooks that pass generation are machine-executable without parsing errors during implementation**.

## Acceptance Criteria

- [ ] **AC-1**: `RunbookStep`, `ModifyBlock`, `SearchReplaceBlock`, `NewBlock`, and `DeleteBlock` Pydantic models are defined in a new `models.py` module under `.agent/src/agent/core/implement/`.
- [ ] **AC-2**: `validate_runbook_schema()` in `parser.py` is replaced by a Pydantic-based validator that returns a `List[str]` of human-readable violation messages (preserving the existing contract) while using Pydantic models internally for structural validation.
- [ ] **AC-3**: `runbook.py` parses AI output into the new Pydantic models before writing to disk. On `ValidationError`, the exact error is fed back to the LLM as a correction prompt (iterative retry, max 3 attempts per ADR-012).
- [ ] **AC-4**: `ModifyBlock` validators enforce: (a) `<<<SEARCH` block is present, (b) search text is non-empty, (c) file path does not reference non-existent directories.
- [ ] **AC-5**: `NewBlock` validators enforce: (a) fenced code block content is non-empty, (b) no `<<<SEARCH` blocks appear (these go to `ModifyBlock`).
- [ ] **AC-6**: All existing `parser.py` unit tests continue to pass with the new Pydantic backend.
- [ ] **Negative Test**: A deliberately malformed runbook (empty SEARCH blocks, hallucinated paths) is rejected with a clear, actionable error message before any file is written.

## Non-Functional Requirements

- Performance: Pydantic V2 compiled validators must add < 50ms overhead to runbook generation.
- Security: No PII or secrets in validation error logs.
- Compliance: ADR-012 retry patterns used for self-correction loop.
- Observability: Validation failures emitted as structured log events with `validation_error` field.

## Linked ADRs

- ADR-012 (Retry and Backoff Utilities)
- ADR-005 (AI-Driven Governance Preflight)

## Linked Journeys

- JRN-065

## Impact Analysis Summary

Components touched: `parser.py`, `runbook.py`, `orchestrator.py`, new `models.py`
Workflows affected: `/runbook`, `/implement`
Co-committed: Feature iceboxing changes from plan INFRA-129 are included in this branch.
Risks identified: LLM may struggle with strict JSON/YAML output — mitigated by iterative retry with Pydantic error feedback.

## Test Strategy

- Unit tests: synthetic malformed runbooks must trigger `ValidationError`.
- Integration test: `agent new-runbook` on a COMMITTED story must produce a schema-valid runbook or retry and report clear errors.
- Regression: all existing `test_parser.py` and `test_implement*.py` tests pass unchanged.

## Rollback Plan

Revert to the regex-based `validate_runbook_schema()` by restoring `parser.py` to its pre-change state. The Pydantic models module can remain as dead code until re-enabled.

## Copyright

Copyright 2026 Justin Cook
