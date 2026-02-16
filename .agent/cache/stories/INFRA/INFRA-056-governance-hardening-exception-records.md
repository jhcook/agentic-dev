# INFRA-056: Governance Hardening — Exception Records & Preflight Precision

## State

COMMITTED

## Problem Statement

The AI-driven preflight governance system (ADR-005) produces **recurring false positives** due to ambiguous rules. Specifically:

1. **No formal rebuttal mechanism**: When a preflight finding is successfully challenged, there is no way to persist the rebuttal. The same false positive recurs on every subsequent run.
2. **Undefined layer boundaries**: The @Architect role invents contradictory module dependency rules between runs because no authoritative boundary map exists.
3. **Undefined "breaking change"**: The @QA role flags internal improvements (e.g., widening a utility function's behavior) as breaking changes because no scoped definition exists.
4. **Copy-paste bug in roles**: §6 @Observability in `the-team.mdc` was a verbatim copy of §4 @Docs, producing incorrect governance checks.

These issues waste review cycles, erode confidence in the governance system, and generate audit noise.

## User Story

As a **developer governed by the agent framework**, I want preflight checks to be **precise and non-repetitive** so that I only address genuine violations and don't waste time rebuting false positives on every commit.

## Acceptance Criteria

- [x] **AC-1**: An ADR (ADR-021) establishes Exception Records (`EXC-*`) as a formal ADR subtype with lifecycle management (Accepted → Superseded → Retired).
- [x] **AC-2**: An exception record template exists at `.agent/templates/exception-template.md` with fields: Status, Challenged By, Rule Reference, Affected Files, Justification, Conditions.
- [x] **AC-3**: The `/preflight` workflow loads active `EXC-*` records before role reviews and suppresses matching challenges.
- [x] **AC-4**: `adr-standards.mdc` documents `EXC-*` as a recognised ADR subtype.
- [x] **AC-5**: `architectural-standards.mdc` defines explicit layer boundaries with "IS / ISN'T a violation" sections, applicable to all managed codebases, with the agent CLI as a documented example.
- [x] **AC-6**: `breaking-changes.mdc` defines what constitutes a breaking change vs. an internal improvement, with a concrete verification checklist.
- [x] **AC-7**: §6 @Observability in `the-team.mdc` contains observability-specific responsibilities (structured logging, tracing, PII-safe logs), not a copy of @Docs.
- [ ] **Negative Test**: A preflight run with active `EXC-*` records does not raise BLOCK for findings covered by accepted exceptions.

## Non-Functional Requirements

- **Compliance**: Exception records provide SOC 2 audit evidence for justified deviations.
- **Universality**: New rules (`breaking-changes.mdc`, `architectural-standards.mdc`) apply to all codebases managed by the agent, not just the agent's own code.
- **Maintainability**: Exception records follow the same immutability and change-logging rules as standard ADRs.

## Linked ADRs

- ADR-005 (AI-Driven Governance Preflight)
- ADR-021 (Architectural Exception Records) — **introduced by this story**

## Impact Analysis Summary

Components touched:

- `.agent/adrs/` — new ADR-021, new EXC-001
- `.agent/templates/` — new exception-template.md
- `.agent/rules/` — modified `adr-standards.mdc`, `architectural-standards.mdc`, `the-team.mdc`; new `breaking-changes.mdc`
- `.agent/workflows/preflight.md` — new LOAD EXCEPTIONS step

Workflows affected:

- `/preflight` — now loads exception records before role reviews
- `/commit` — indirectly, as preflight precision reduces false blocks

Risks identified:

- Stale exceptions: If conditions are not reviewed, exceptions may outlive their validity. Mitigated by the `Conditions` field.

## Test Strategy

- Run `/preflight` on a changeset that would previously trigger the `update_story_state` location challenge.
- Verify EXC-001 suppresses the finding and references the exception record.
- Verify unrelated findings still produce BLOCK as expected.

## Rollback Plan

- Delete `EXC-*` files and ADR-021 to remove exception support.
- Revert the LOAD EXCEPTIONS step from `preflight.md`.
- Revert additions to `adr-standards.mdc`.
- The new rules (`breaking-changes.mdc`, merged `architectural-standards.mdc`) are additive and can remain.
