# INFRA-155: Harden Implement Pipeline — Runbook Self-Healing and Gate Relaxation

## State

COMMITTED

## Problem Statement

The `agent implement` pipeline is brittle. AI-generated runbooks frequently fail the docstring gate on nested/inner functions, omit trailing newlines, and use dependencies not declared in the project. This creates a frustrating manual fix cycle on every `implement --apply`. Additionally, `new-runbook` generates code in a single pass with no validation, meaning these issues are baked in from the start.

## User Story

As a **Platform Developer**, I want **`new-runbook` to self-validate generated code against the implement gates before writing to disk** so that **`agent implement --apply` succeeds on the first attempt without manual intervention.**

## Acceptance Criteria

- [ ] **AC-1**: `new-runbook` runs `enforce_docstrings` and trailing-newline checks against all `[NEW]` code blocks before writing the runbook. If violations are found, the AI is re-prompted to fix them (max 2 retries).
- [ ] **AC-2**: The docstring gate in `implement.py` is demoted to a **warning** for nested/inner functions (functions defined inside other functions). Only module-level, class, and top-level function docstrings are hard-enforced.
- [ ] **AC-3**: `new-runbook` validates that all imports in generated code blocks reference packages available in the project's declared dependencies (pyproject.toml).
- [ ] **Negative Test**: A runbook with a nested function missing a docstring passes the gate without blocking.

## Non-Functional Requirements

- Performance: The self-healing loop adds at most one additional AI call per runbook generation.
- Observability: Log the number of self-healing retries and which violations were auto-fixed.

## Linked ADRs

- None

## Linked Journeys

- JRN-057: Impact Analysis Workflow

## Impact Analysis Summary

Components touched: `.agent/src/agent/commands/runbook.py` (MODIFY), `.agent/src/agent/commands/implement.py` (MODIFY), `.agent/src/agent/core/implement/guards.py` (MODIFY)
Workflows affected: `new-runbook`, `implement --apply`
Risks identified: Relaxing docstring gate could reduce code documentation quality — mitigated by keeping hard enforcement on public API surfaces.

## Test Strategy

- Unit test: nested function without docstring passes the relaxed gate.
- Unit test: module-level function without docstring still blocks.
- Integration test: `new-runbook` with intentionally bad code triggers self-healing retry and produces a clean runbook.

## Rollback Plan

Revert the gate relaxation and remove the self-healing loop. No database or schema changes involved.

## Copyright

Copyright 2026 Justin Cook
