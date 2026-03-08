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
- [x] **AC-9 (Implement Gate as Warning)**: `agent implement` post-apply gate failures produce a `⚠️` warning and set story state to `REVIEW_NEEDED` instead of blocking the run. `preflight` remains the hard gatekeeper. Unit tests in `tests/core/check/test_system.py` verify the gate-as-warning path.
- [x] **AC-10 (ADC Project Auto-Detection)**: Vertex AI initialisation falls back to `google.auth.default()` when `GOOGLE_CLOUD_PROJECT` env var is not set, correctly reading `quota_project_id` from the ADC credentials file. Unit test: mock `google.auth.default()` to verify project is picked up.
- [x] **AC-11 (Provider-Aware Diff Truncation)**: ADK orchestrator truncates diffs before sending to the governance council: `gh`→6k chars, `vertex`/`gemini`/`anthropic`→200k chars, default→40k chars. Provider is resolved via `_ensure_initialized()` before the limit is selected (prevents empty-string provider). Unit test: assert correct limit is selected per provider.

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
  - `core/check/__init__.py` (new — facade)
  - `core/ai/service.py` (ADC fallback for Vertex AI, provider fallback priority reordering, neutral warning for unavailable configured provider)
  - `core/adk/orchestrator.py` (provider-aware diff truncation with `_ensure_initialized()` guard)
  - `commands/implement.py` (post-apply governance gates changed from blocking failures to `⚠️` warnings; story state set to `REVIEW_NEEDED` on gate failure)
- **Workflows affected**: `agent check`, `agent preflight`, `agent implement`, AI provider selection on all commands.
- **Risks identified**: `check_journey_coverage` is called both by `check.py` and `governance.py` — its new location must be importable from `governance/validation.py` without circular dependency. Provider fallback reordering changes the implicit fallback sequence for all users not exporting `GOOGLE_CLOUD_PROJECT`.

## Test Strategy

- **Regression**: Run existing `tests/commands/test_check.py` without modification; 100% pass rate required.
- **Unit Testing (decomposition)**: Isolated tests for system check helpers (`validate_linked_journeys`, `check_credentials`) and quality checks (`check_journey_coverage` with mock YAML journey data).
- **Unit Testing (AI provider — AC-10)**: Mock `google.auth.default()` to verify Vertex AI picks up `quota_project_id` from ADC when `GOOGLE_CLOUD_PROJECT` env var is absent. Test graceful failure when ADC returns no project.
- **Unit Testing (diff truncation — AC-11)**: Instantiate `_orchestrate_async` context with mock provider set to `gh`, `vertex`, and unknown; assert correct `_max_diff` limit is selected without hitting the AI.
- **Unit Testing (implement gate — AC-9)**: Mock a gate that returns `GateResult(passed=False)`; assert the implement command prints `⚠️` and sets story state to `REVIEW_NEEDED` rather than raising.
- **Integration**: Run `agent preflight --story INFRA-103` end-to-end after all changes.

## Rollback Plan

- Revert the feature branch to the previous stable commit on `main`.
- Restore `commands/check.py` from git history and remove the `core/check/` package.

## Copyright

Copyright 2026 Justin Cook
