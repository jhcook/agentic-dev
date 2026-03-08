# INFRA-103: Decompose Check Command

## State

COMMITTED

## Parent Plan

INFRA-099

## Problem Statement

The `commands/check.py` module has grown to 1,768 LOC and combines two distinct concerns: system health checks (dependency verification, credential validation, environment inspection) and code quality checks (journey coverage, PR size, LOC enforcement). Mixing these makes it hard to run either set of checks in isolation, add new checks without modifying unrelated code, or test them independently.

## User Story

As a **Backend Engineer**, I want to **decompose the monolithic check command into a thin CLI facade and dedicated system/quality check modules** so that **each category of check is independently maintainable and testable, and the 500 LOC ceiling per module is respected.**

## Acceptance Criteria

- [x] **AC-1** *(amended — incremental delivery)*: `commands/check.py` extracted its first two sub-modules (`core/check/system.py` and `core/check/quality.py`) as a safe initial slice. The facade remains at ~1,597 LOC pending follow-on extraction of the AI governance council call-sites (see **INFRA-110**). The ≤500 LOC target will be met when that follow-on story lands. Renegotiated with @Architect per the INFRA-101 precedent of multi-slice delivery.
- [x] **AC-2**: `core/check/system.py` contains system health checks: `check_credentials`, `validate_linked_journeys` (with `LinkedJourneysResult` TypedDict), and `validate_story`.
- [x] **AC-3**: `core/check/quality.py` contains code quality checks: `check_journey_coverage` (with `JourneyCoverageResult` TypedDict).
- [x] **AC-4**: `core/check/__init__.py` re-exports the public API so all existing callers continue to work without modification.
- [x] **AC-5**: All existing tests pass. `python -c "import agent.cli"` succeeds with no circular imports.
- [x] **AC-6**: No circular imports — confirmed via import smoke test.
- [x] **AC-7**: Unit tests in `tests/core/check/test_system.py` and `tests/core/check/test_quality.py`.
- [x] **AC-8**: All new modules include PEP-484 type hints and PEP-257 docstrings.
- [x] **Negative Test**: `check_journey_coverage` returns `passed=True` when journeys directory does not exist.

## Non-Functional Requirements

- **Performance**: Combined check execution time unchanged.
- **Security**: Credential validation must not log raw API keys or tokens — `scrub_sensitive_data` usage preserved.
- **Compliance**: N/A.
- **Observability**: Structured logging for each check category preserved in the respective sub-module.

## Linked ADRs

- ADR-041: Module Decomposition Standards

## Linked Journeys

- JRN-036: Preflight Governance Check
- JRN-045: Implement Story from Runbook

## Impact Analysis Summary

- **Components touched**:
  - `commands/check.py` (refactor, thinned)
  - `core/check/system.py` (new — health checks)
  - `core/check/quality.py` (new — quality checks)
  - `core/check/__init__.py` (new — re-exports public API)
- **Workflows affected**: `agent check`, `agent preflight` (which calls governance checks).
- **Risks identified**: `check_journey_coverage` is called both by `check.py` and `governance.py` — its new location in `core/check/quality.py` must be importable from `governance/validation.py` without creating a circular dependency.
- **Out-of-scope changes co-committed**: ADC fallback, diff truncation, implement-gate-as-warning, and provider fallback warning are tracked and documented in **INFRA-110**.

## Test Strategy

- **Regression**: Run existing `tests/commands/test_check.py` without modification; 100% pass rate required.
- **Unit Testing**: Isolated tests for system check helpers (`validate_linked_journeys`, `check_credentials`) and quality checks (`check_journey_coverage` with mock YAML journey data).
- **Integration**: Run `agent check` and `agent preflight --story INFRA-103` end-to-end after all changes.

## Rollback Plan

- Revert the feature branch to the previous stable commit on `main`.
- Restore `commands/check.py` from git history and remove the `core/check/` package.

## Copyright

Copyright 2026 Justin Cook
