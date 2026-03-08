# INFRA-109: Fix resolve_path to Skip Fuzzy Search for Trusted-Prefix Paths

## State

COMMITTED

## Problem Statement

`resolve_path` in `agent.core.implement.orchestrator` performs a fuzzy
filename match (via `_find_file_in_repo`) even when the supplied path starts
with a trusted root prefix (`.agent/`, `agent/`, `backend/`, `web/`,
`mobile/`). This causes silent redirection to an *existing* file with the
same basename — most visibly, `.agent/tests/core/implement/test_orchestrator.py`
was silently overwritten into `.agent/tests/voice/test_orchestrator.py` during
the INFRA-102 `agent implement` run. The trusted-prefix heuristic is applied
only to the *directory-not-found* branch, not to the *file-already-exists-elsewhere*
branch, which is the wrong priority order.

## User Story

As a developer running `agent implement`, I want explicit `.agent/…` file paths
in runbook `[NEW]` steps to land exactly where specified, so that the implement
pipeline is predictable and does not silently corrupt unrelated files.

## Acceptance Criteria

- [ ] **AC-1 Trusted Prefix Short-Circuits Fuzzy Match**: Given a path whose
  prefix is in `TRUSTED_ROOT_PREFIXES` and the file does not yet exist, when
  `resolve_path` is called, then it returns the path as-is without calling
  `_find_file_in_repo`.
- [ ] **AC-2 Non-Trusted Path Still Fuzzy-Matches**: Given a path like
  `custom_script.py` (no trusted prefix), when a unique git match exists,
  then `resolve_path` auto-corrects as before.
- [ ] **AC-3 Regression Test**: `test_implement_pathing.py::test_apply_auto_correct`
  and the two new AC-1/AC-2 tests all pass.
- [ ] **AC-4 No Other Test Regressions**: Full suite `tests/commands/` and
  `tests/core/implement/` passes.

## Non-Functional Requirements

- No observable performance change — the early return avoids a subprocess call.
- Structured log warning when a non-trusted path is auto-corrected.

## Linked ADRs

- ADR-016 (CLI tool quality)

## Linked Journeys

- JRN-045
- JRN-072

## Impact Analysis Summary

Components touched: `.agent/src/agent/core/implement/orchestrator.py`
Workflows affected: `agent implement` path resolution
Risks identified: Low — change only tightens resolution for paths that already
  have an explicit root prefix. Non-prefixed paths behave identically.

## Test Strategy

Unit tests in `tests/core/implement/test_orchestrator.py` covering:
1. A `.agent/`-prefixed path that does not exist → returned as-is (no subprocess).
2. An unprefixed path with a unique match → auto-corrected as before.

## Rollback Plan

Revert the two-line guard addition to `resolve_path`. No data migrations.

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0.
