# INFRA-092: Post-Apply PR Size Gate

## State

COMMITTED

## Problem Statement

The framework lacks programmatic enforcement of PR size limits. Large PRs cause "context stuffing" hallucinations in AI governance checks. This is Layer 5 of the INFRA-089 defence-in-depth strategy.

## User Story

As a **developer using the agentic-dev framework**, I want **an automated PR size gate that rejects PRs exceeding 400 LOC** so that **AI governance checks remain accurate and PRs stay reviewable**.

## Acceptance Criteria

- [ ] **AC-1 (PR Size Gate)**: >400 LOC in `git diff --cached` → REJECT.
- [ ] **AC-2 (Exceptions — Automated)**: PRs with `chore(deps):` or `refactor(auto):` prefix bypass the threshold.
- [ ] **AC-3 (Exceptions — Deletions)**: Net-negative PRs (more deletions than additions) are exempt.
- [ ] **AC-4 (Exceptions — Data/Assets)**: Changes to `.json`, `.yaml`, `.png`, etc. are excluded from LOC count.
- [ ] **AC-5 (Wiring)**: `check_pr_size` is called in the post-apply governance gates section of `implement.py`.
- [ ] **Negative**: Under-limit PR passes the gate without warnings.

## Non-Functional Requirements

- Performance: `check_pr_size` executes in <1s.
- Compliance: Follows existing `GateResult` pattern.
- Observability: Structured log with `total_loc`, `threshold`, `decision`.

## Linked ADRs

- ADR-005 (AI-Driven Governance Preflight)

## Linked Journeys

- JRN-065 — Circuit Breaker During Implementation

## Impact Analysis Summary

Components touched: `gates.py`, `implement.py`
Workflows affected: `/implement`, `/preflight`
Risks: Exception detection regex accuracy for commit prefixes

## Test Strategy

- Unit: `check_pr_size` — under-limit → pass, over-limit → reject, deletions exempt, data files exempt, automated prefix exempt
- Integration: Verify wiring in `implement.py` post-apply gates section

## Rollback Plan

Revert additions to `gates.py`, `implement.py`, and `test_gates.py`. No migrations or config changes.

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0
