# INFRA-095: Micro-Commit Loop and Circuit Breaker

## State

IN_PROGRESS

## Problem Statement

The `/implement` command generates all code in a single pass without enforcing commit atomicity or cumulative size limits. This allows unbounded output that degrades traceability, makes rollbacks difficult, and produces oversized PRs. This is Layer 3 of the INFRA-089 defence-in-depth strategy.

## User Story

As a **developer using the agentic-dev framework**, I want **a micro-commit implement loop with save points, small-step enforcement, and a LOC circuit breaker** so that **each implementation step is auto-committed atomically, and oversized implementations are gracefully split into follow-up stories**.

## Acceptance Criteria

- [ ] **AC-1 (Save Points)**: Each Runbook step triggers: generate code → apply → test → green → auto-commit.
- [ ] **AC-2 (Small-Step)**: Max 30 lines edit distance per step enforced before pausing to test and commit.
- [ ] **AC-3 (LOC Warning)**: 200 cumulative LOC → warning displayed to developer.
- [ ] **AC-4 (Circuit Breaker)**: 400 cumulative LOC → commit partial work, auto-generate follow-up story, print guidance, exit 0.
- [ ] **AC-5 (Follow-Up Story)**: Follow-up story references remaining Runbook steps and uses the next available story ID.
- [ ] **AC-6 (Plan Linkage)**: If no Plan exists, create one linking original and follow-up. If Plan exists, append.
- [ ] **Negative**: Runbook completing within 400 LOC limit runs to completion without circuit breaker.

## Non-Functional Requirements

- Performance: LOC counting and save-point commits add <2s overhead per step.
- Compliance: Audit logging for circuit breaker and save-point events (SOC2).
- Observability: Structured logs for step completion, LOC thresholds, circuit breaker activation.

## Linked ADRs

- ADR-005 (AI-Driven Governance Preflight)

## Linked Journeys

- JRN-065 — Circuit Breaker During Implementation

## Impact Analysis Summary

Components touched: `implement.py`
Workflows affected: `/implement`
Risks: Test execution overhead per save-point. Follow-up story ID collision. Mid-step circuit breaker atomicity.

## Test Strategy

- Unit: `count_edit_distance` — single file, multiple files, empty blocks
- Unit: `create_follow_up_story` — correct ID, contains remaining steps, no overwrite
- Integration: Mock implement loop exceeding 400 LOC → circuit breaker fires → partial commit + follow-up story
- Integration: Under-limit → completes normally. 200 LOC → warning logged.

## Rollback Plan

Revert additions to `implement.py` and `test_implement_circuit_breaker.py`. No migrations or config changes.

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0
