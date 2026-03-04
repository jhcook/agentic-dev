# INFRA-091: Static Commit Atomicity Checks

## State

COMMITTED

## Problem Statement

The framework has no programmatic enforcement of commit-level atomicity. Large, compound commits pass through without warning, degrading AI review quality and making changes harder to trace or revert. This is Layer 4 of the INFRA-089 defence-in-depth strategy.

## User Story

As a **developer using the agentic-dev framework**, I want **static checks that warn on oversized commits, compound commit messages, and cross-domain changes** so that **each commit represents a single, reversible logical unit**.

## Acceptance Criteria

- [ ] **AC-1 (20/100 Rule)**: Warn if >20 lines changed in a single file OR >100 lines total across the commit.
- [ ] **AC-2 (And Test)**: Warn if commit message contains "and" joining two distinct actions.
- [ ] **AC-3 (Conventional Commit)**: Reject if commit message can't be described by a single conventional commit type prefix.
- [ ] **AC-4 (Domain Isolation)**: FAIL if commit touches both `core/` and `addons/` subtrees.
- [ ] **Negative**: Under-limit commit with single-type prefix passes all checks without warnings.

## Non-Functional Requirements

- Performance: All static checks execute in <1s.
- Compliance: Uses existing `GateResult` return pattern and `log_skip_audit` for consistency.
- Observability: Structured logs for threshold violations.

## Linked ADRs

- ADR-005 (AI-Driven Governance Preflight)

## Linked Journeys

- JRN-065 — Circuit Breaker During Implementation (Layer 4 feeds into Layer 3's save-point validation)

## Impact Analysis Summary

Components touched: `gates.py`
Workflows affected: `/commit`, `/preflight`
Risks: "And" test false positives on legitimate compound words (e.g., "command")

## Test Strategy

- Unit: `check_commit_size` — over-limit per file, over-limit total, under-limit, empty changeset
- Unit: `check_commit_message` — compound "and" message, single-type prefix, multi-type rejection, edge cases
- Unit: `check_domain_isolation` — mixed core/addons → fail, single domain → pass

## Rollback Plan

Revert additions to `gates.py` and `test_gates.py`. No migrations or config changes.

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0
