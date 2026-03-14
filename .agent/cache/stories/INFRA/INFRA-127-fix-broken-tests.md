# INFRA-127: Fix broken tests

## State

ACCEPTED

## Problem Statement

The test suite on main has 9 failures across 5 test files plus 1 collection error, preventing reliable preflight checks and CI/CD. Root causes include: (1) missing `pytest-asyncio` plugin for async tests, (2) test assertions drifted from refactored module paths in `main.py`, (3) ADC fallback path not mocked in vertex credential test, (4) module-level import of optional `opentelemetry.exporter` package, and (5) preflight's smart test selection explicitly excluding `.agent/` framework tests — creating a regression blind spot where core tests never run as a hard-blocking gate.

## User Story

As a developer I want the test suite to pass on main so that I can rely on CI/CD and preflight checks.

## Acceptance Criteria

- [x] **AC-1**: All async tests (`test_retry_async_*`, `test_jitter_and_backoff_calculation`, `test_executor_loop_guardrail_integration`) pass without `pytest-asyncio` by using explicit `asyncio.run()`.
- [x] **AC-2**: `test_vertex_fails_without_project` mocks the ADC fallback path so it fails correctly in dev environments where `~/.config/gcloud/application_default_credentials.json` exists.
- [x] **AC-3**: `test_impact_requires_creds` and `test_panel_requires_creds` accept both legacy (`check.impact`) and current (`impact.impact`) module paths.
- [x] **AC-4**: `test_verifier.py` collects successfully by lazy-importing `OTLPSpanExporter` inside `initialize_telemetry()` instead of at module level in `telemetry.py`.
- [x] **AC-5**: `preflight`'s smart test selection (`testing.py`) includes `.agent/` framework tests as a hard-blocking gate when `.agent/` files are modified, using the same `agent.yaml` test_commands config that `implement` uses.
- [x] **AC-6**: `agent preflight` passes on this story branch with the test fixes.

## Non-Functional Requirements

N/A

## Linked ADRs

- ADR-012 (Retry and Backoff)
- ADR-025 (Observability)

## Linked Journeys

- JRN-009

## Impact Analysis Summary

**Files Changed**: 6

| File | Change |
|---|---|
| `agent/core/check/testing.py` | Added `.agent/` framework test strategy to smart test selection |
| `agent/core/telemetry.py` | Lazy import of `OTLPSpanExporter` |
| `agent/core/ai/tests/test_vertex_provider.py` | Mock `Path.home()` for ADC fallback |
| `agent/core/auth/tests/test_regression_credentials.py` | Accept refactored module paths |
| `agent/core/implement/tests/test_retry.py` | Replace `@pytest.mark.asyncio` with `asyncio.run()` |
| `agent/core/tests/test_guardrails.py` | Replace `@pytest.mark.asyncio` with `asyncio.run()` |

**Blast Radius**: Low — test fixes and one infrastructure fix (testing.py).
**Risks identified**: None — all changes are additive or corrective.

## Test Strategy

Run `cd .agent/src && python3 -m pytest agent/ -q --tb=short`. Result: 146 passed, 1 skipped, 4 xfailed, 0 failures.

## Rollback Plan

Revert the commit.

## Copyright

Copyright 2026 Justin Cook
