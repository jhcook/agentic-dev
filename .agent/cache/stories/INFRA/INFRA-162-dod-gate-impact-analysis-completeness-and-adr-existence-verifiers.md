# INFRA-162: DoD Gate: Impact Analysis Completeness and ADR Existence Verifiers

## State

COMMITTED

## Problem Statement

The Definition of Done (DoD) Compliance Gate (Gate 4) fails to catch two critical discrepancies during the preflight process:
1. **Impact Analysis Gaps**: Emergent files created or modified during implementation are often omitted from the final Step N Impact Analysis block because the AI generates that block before implementation concludes.
2. **Hallucinated ADRs**: The system currently accepts ADR-NNN references that do not exist in the on-disk catalogue, leading to downstream false-positive blocks by security and product validators.

## User Story

As an **Infrastructure Engineer**, I want **deterministic verifiers for Impact Analysis and ADR references** so that **I can reduce preflight iterations and prevent pipeline failures caused by incomplete documentation or hallucinated references.**

## Acceptance Criteria

- [ ] **Scenario 1**: Given a runbook containing `[NEW]`, `[MODIFY]`, or `[DELETE]` operations, When Gate 4 runs, Then `_gap_4f` must verify that every referenced path (excluding `CHANGELOG.md` and the story file) exists within the Step N Impact Analysis replacement text.
- [ ] **Scenario 2**: `_gap_4g` must extract all `ADR-NNN` patterns from the runbook and validate them against the current on-disk ADR catalogue; any citation of a non-existent ADR must trigger a failure.
- [ ] **Negative Test**: System handles empty runbooks or missing ADR directories gracefully without throwing unhandled exceptions.

## Non-Functional Requirements

- **Performance**: Verifiers must be deterministic (regex/set operations) and execute in <200ms to avoid pipeline lag.
- **Security**: No AI-based reasoning allowed for these checks to prevent bypass via prompt injection.
- **Compliance**: Ensure 100% parity between implementation artifacts and the Impact Analysis summary.
- **Observability**: Provide clear error messaging indicating exactly which files are missing from the Impact Analysis or which ADR IDs are invalid.

## Linked ADRs

- ADR-005: AI-Driven Governance Preflight
- ADR-040: Agentic Tool-Calling Loop Architecture

## Linked Journeys

- JRN-057: Impact Analysis Workflow
- JRN-062: Implement Oracle Preflight Pattern

## Impact Analysis Summary

**Components touched:**
- `.agent/src/agent/commands/runbook.py` — **[MODIFY]** Wire `_gap_4f` and `_gap_4g` into Gate 4 `dod_gaps` list.
- `.agent/src/agent/core/implement/guards.py` — **[MODIFY]** Implement `check_impact_analysis_completeness`, `check_adr_refs`, and `check_op_type_vs_filesystem` verifier functions; fix `check_imports` pyproject.toml resolution and namespace package handling.
- `.agent/src/agent/core/implement/tests/test_guards.py` — **[NEW]** Unit tests for all verifiers covering happy path, missing paths, hallucinated ADRs, op-type mismatches, and empty/missing inputs.
- `CHANGELOG.md` — **[MODIFY]** Document new verifiers.


**Workflows affected:**
- DoD Compliance Gate (Gate 4)
- Preflight validation pipeline

**Risks identified:**
- Potential for false positives if file paths in the runbook use inconsistent formatting (mitigated by path normalization).

## Test Strategy

- **Unit Testing**: Implement tests in `tests/test_runbook_verifiers.py` using mock runbook content and mock file systems to verify set-intersection logic for both `_gap_4f` and `_gap_4g`.
- **Integration Testing**: Execute a sample implementation flow to ensure emergent files (e.g., `utils.py`) are correctly caught when missing from the final summary.

## Rollback Plan

- Revert changes to `agent/commands/runbook.py` and remove the associated unit tests to return to the previous Gate 4 logic.

## Copyright

Copyright 2026 Justin Cook
