# INFRA-089: Enforce Atomic Development PR and Commit Size Limits

## State

COMMITTED

## Problem Statement

Large PRs cause "Context Stuffing" hallucinations in Oracle Preflight checks and reduce code generation fidelity. The framework has no mechanism to enforce PR or commit size limits, allowing Stories to produce unbounded output that degrades AI review quality and developer productivity.

## User Story

As a **developer using the agentic-dev framework**, I want **automated enforcement of PR size limits (200–400 LOC), atomic commit rules, and micro-commit workflows** so that **AI governance checks remain accurate, commits are reversible and traceable, and each change represents a single logical unit**.

## Architecture: Five Defence Layers

### Layer 1 — Forecast Gate (Primary Defence)
Before Runbook generation, estimate complexity with a lightweight AI call. If the Story is over-budget, generate a **Plan** with decomposed child Stories instead of a Runbook.

**Thresholds:** >400 LOC estimated, >8 steps, >4 files.

**Complexity Score** calculated from three factors:
- **Step Count**: >8 steps = too big.
- **Context Width**: >4 distinct files = too wide.
- **Verb Intensity**: Heavy verbs (Refactor, Migrate, Rewrite) multiply estimated size by 2x.

`--skip-forecast` flag available with audit logging.

### Layer 2 — SPLIT_REQUEST Fallback (Secondary Defence)
The Runbook Agent's system prompt includes a Complexity Gatekeeper directive. If after generating a Runbook the AI detects it's over-limit, it emits a `SPLIT_REQUEST` JSON instead. The framework parses this, writes decomposition suggestions to `.agent/cache/split_requests/`, and exits with code 2.

### Layer 3 — Micro-Commit Implement Loop
The `/implement` command enforces atomicity during code generation:

**A. Save Point Strategy:** Commit after every successful "green" state (tests pass). Each Runbook step = one commit cycle:
1. Agent generates code for step
2. Apply changes
3. Run tests
4. Green → auto-commit. Red → fix, then re-test.

**B. Small-Step Loop:** Max 30 lines edit distance per step before pausing to test and commit. Prevents context-stuffing spirals.

**C. Circuit Breaker:** Cumulative LOC tracker. 200 LOC → warn. 400 LOC → stop, audit-log, request follow-up Story.

### Layer 4 — Commit Atomicity Checks
Static checks run at commit time:

- **20/100 Rule:** Warn if >20 lines changed in a single file OR >100 lines total across the commit.
- **"And" Test:** Warn if commit message contains "and" joining two distinct actions.
- **Multi-File Scope:** Warn if >5 files in a single commit (excluding global renames).
- **Conventional Commit Lint:** Reject commits that can't be described by a single type (`feat:`, `fix:`, `refactor:`, etc.).

### Layer 5 — Post-Apply PR Gates
Final verification in the governance pipeline:

- `check_pr_size`: PASS ≤400 LOC / REJECT >400 LOC on `git diff --cached`.
- `check_domain_isolation`: FAIL if PR touches both `core/` and `addons/`.

### Exceptions — Acceptable Large PRs
The following scenarios bypass or raise the LOC threshold:

- **Automated Changes**: Large-scale dependency updates or automated refactoring (e.g., tool-driven library updates across the repo). Detectable by commit message prefix `chore(deps):` or `refactor(auto):`.
- **Deletions**: PRs that are net-negative (more deletions than additions) are exempt. Removing dead code has lower cognitive load than adding new code.
- **Data/Asset Updates**: Changes to JSON schema definitions, configuration files, or large asset commits (images, fixtures). Detectable by file extension (`.json`, `.yaml`, `.png`, etc.).

## Acceptance Criteria

- [ ] **AC-1 (Forecast)**: Over-budget Story → Plan with child Stories generated, exit 2.
- [ ] **AC-2 (SPLIT_REQUEST)**: SPLIT_REQUEST JSON detected → parsed, saved, exit 2.
- [ ] **AC-3 (Save Points)**: Each Runbook step triggers test → green → auto-commit.
- [ ] **AC-4 (Small-Step)**: Max 30 lines edit distance per step enforced.
- [ ] **AC-5 (Circuit Breaker)**: 200 LOC warn, 400 LOC stop.
- [ ] **AC-6 (20/100 Rule)**: >20 lines/file or >100 total → warn.
- [ ] **AC-7 (And Test)**: Compound commit messages → warn.
- [ ] **AC-8 (Conventional Commit)**: Multi-type prefix → reject.
- [ ] **AC-9 (PR Size Gate)**: >400 LOC → REJECT.
- [ ] **AC-10 (Domain Isolation)**: core/ + addons/ mixed → FAIL.
- [ ] **Negative**: Under-limit Story proceeds normally through all layers.

## Non-Functional Requirements

- Performance: All static checks (`check_pr_size`, `check_commit_size`, `check_domain_isolation`) <1s.
- Compliance: Audit logging for circuit breaker, split, and save-point events (SOC2).
- Observability: Structured logs for forecast decisions, SPLIT_REQUEST, threshold violations.
- Rules: `.agent/rules/` are already loaded by `implement` as AI advisory instructions; these gates add **programmatic** enforcement.

## Linked ADRs

- ADR-005 (AI-Driven Governance Preflight)

## Linked Journeys

- N/A

## Impact Analysis Summary

Components touched: `gates.py`, `runbook.py`, `implement.py`
Workflows affected: `/runbook`, `/implement`, `/commit`, `/preflight`
Risks: Forecast accuracy; "And" test false positives; test execution overhead per save-point

## Test Strategy

- Unit: `check_pr_size`, `check_commit_size`, `check_commit_message`, `check_domain_isolation`, `score_runbook_complexity`
- Unit: Forecast gating, SPLIT_REQUEST detection in `runbook.py`
- Integration: Save-point loop, small-step edit distance, LOC circuit breaker in `implement.py`

## Rollback Plan

Revert `gates.py`, `runbook.py`, `implement.py` and their tests. No migrations or config schema changes.

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0
