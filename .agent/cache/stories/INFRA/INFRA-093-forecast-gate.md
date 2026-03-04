# INFRA-093: Forecast Gate for Runbook Generation

## State

COMMITTED

## Problem Statement

Stories that exceed complexity thresholds produce oversized Runbooks that cause context-stuffing hallucinations during implementation. There is no pre-generation check to detect and decompose over-budget stories. This is Layer 1 of the INFRA-089 defence-in-depth strategy.

## User Story

As a **developer using the agentic-dev framework**, I want **a forecast gate that detects over-budget stories before runbook generation and produces a Plan with decomposed child stories** so that **each implementation stays within atomic PR limits**.

## Acceptance Criteria

- [ ] **AC-1 (Complexity Score)**: `score_story_complexity` calculates step count, context width, verb intensity, and estimated LOC from story content.
- [ ] **AC-2 (Forecast Gate)**: Over-budget story (>400 LOC, >8 steps, or >4 files) → Plan generated, exit code 2.
- [ ] **AC-3 (Plan Output)**: Plan file created in `.agent/cache/plans/` with child story references, each scoped to ≤400 LOC.
- [ ] **AC-4 (Skip Flag)**: `--skip-forecast` bypasses the gate with `log_skip_audit` and structured audit fields.
- [ ] **AC-5 (Under Budget)**: Under-limit story proceeds to normal runbook generation.

## Non-Functional Requirements

- Performance: Complexity scoring is heuristic-based, <100ms (no AI call for scoring; AI only for Plan generation).
- Compliance: `--skip-forecast` bypass audit-logged (SOC2).
- Observability: Structured log with `step_count`, `context_width`, `verb_intensity`, `estimated_loc`, `decision`.

## Linked ADRs

- ADR-005 (AI-Driven Governance Preflight)

## Linked Journeys

- JRN-064 — Forecast-Gated Story Decomposition

## Impact Analysis Summary

Components touched: `runbook.py`
Workflows affected: `/runbook`
Risks: Forecast accuracy — heuristic may under/overestimate. Layer 2 (INFRA-094) provides a safety net.

## Test Strategy

- Unit: `score_story_complexity` — over-budget story, under-budget, verb intensity multiplier, boundary cases
- Integration: Forecast gate triggers exit code 2 + Plan created; skip-forecast logged

## Rollback Plan

Revert additions to `runbook.py` and `test_runbook_forecast.py`. No migrations or config changes.

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0
