# INFRA-137: Preflight Rationalization

## State

REVIEW_NEEDED

## Problem Statement

`agent preflight` currently performs exhaustive capability checks across `check.py` (28KB, 938 LOC) and `gates.py` (21KB). Many of these checks duplicate validation that will be structurally enforced earlier in the pipeline after INFRA-134 (Pydantic validation) and INFRA-136 (scope guardrails) are implemented. Running a full preflight adds significant cycle time and creates a single-point-of-failure late in the workflow.

## User Story

As a **developer**, I want **preflight to be a lightweight final verification** so that **cycle times are reduced and validation is shifted to where errors are introduced rather than caught after the fact**.

## Acceptance Criteria

- [ ] **AC-1**: Audit `check.py` and `gates.py` to identify checks that are now structurally covered by Pydantic validation (INFRA-134) or Langfuse scope-bounding (INFRA-136).
- [ ] **AC-2**: Deduplicated checks are removed from preflight and documented as "enforced at source" in a migration note.
- [ ] **AC-3**: Preflight is reduced to: lint pass, test pass, and a lightweight schema sanity check.
- [ ] **AC-4**: Preflight execution time is reduced by ≥40% compared to the pre-INFRA-133 baseline.
- [ ] **AC-5**: A `preflight_timing` structured log event captures start-to-finish latency for benchmarking.
- [ ] **Negative Test**: Removing a structurally-enforced check from preflight does not allow a malformed change to pass — the upstream validator (Pydantic or Langfuse) rejects it.

## Non-Functional Requirements

- Performance: Preflight completes in ≤ 30s for a typical story (currently 60s+).
- Security: No relaxation of security-related checks — these remain in preflight.
- Compliance: SOC2 — audit log of removed checks with justification.
- Observability: `preflight_timing` log event with `duration_ms`, `checks_run`, `checks_skipped`.

## Linked ADRs

- ADR-005 (AI-Driven Governance Preflight)

## Linked Journeys

- JRN-065

## Impact Analysis Summary

Components touched: `check.py`, `gates.py`
Workflows affected: `/preflight`, `/pr`
Risks identified: Over-pruning could allow defects to slip — mitigated by dependency ordering (this story is only implemented AFTER INFRA-134 and INFRA-136).

## Test Strategy

- Benchmark: measure preflight execution time before and after; assert ≥40% reduction.
- Regression: all existing preflight tests pass — none of the remaining checks are weakened.
- Negative test: inject a malformed change and verify it's caught by upstream validation, not by preflight.

## Rollback Plan

Re-enable the removed checks in `check.py` and `gates.py` from the backup/diff.

## Copyright

Copyright 2026 Justin Cook
