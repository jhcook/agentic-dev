# INFRA-056: Governance Hardening — Exception Records & Preflight Precision

## State

ACCEPTED

## Goal Description

Introduce a formal mechanism for persisting preflight rebuttals (Architectural Exception Records), harden governance rules to eliminate recurring false positives, and fix the copy-paste bug in `the-team.mdc`. All changes are governance-layer only — no application logic is modified.

## Panel Review Findings

### @Architect — APPROVE

- **ADR-021** follows the established ADR format and correctly extends the existing governance framework.
- The `EXC-*` lifecycle (Accepted → Superseded → Retired) integrates cleanly with the existing ADR status model defined in `adr-standards.mdc`.
- Merging `layer-boundaries.mdc` into `architectural-standards.mdc` avoids rule duplication.
- The codebase-specific boundary map for the agent CLI is accurate and matches the actual import graph.
- **No architectural concerns.**

### @Security — APPROVE

- No secrets, credentials, or PII are involved in any of these changes.
- Exception records do not bypass security checks — they only suppress previously-rebutted architectural findings.
- The `breaking-changes.mdc` rule explicitly preserves security-related breaking change detection (e.g., changing authentication requirements is still BLOCK).
- **No security concerns.**

### @QA — APPROVE

- The changes are governance rules and documentation — no application logic is modified.
- Existing unit tests are unaffected.
- The `breaking-changes.mdc` rule provides a concrete 3-question verification checklist, reducing subjective judgment.
- The `@Observability` fix in `the-team.mdc` ensures the correct checks are applied during future reviews.
- **Recommendation**: After implementation, run `/preflight` on a test changeset to confirm exception suppression works as expected.

### @Docs — APPROVE

- ADR-021 is self-documenting.
- `adr-standards.mdc` updated to document `EXC-*` as a recognised subtype.
- CHANGELOG should be updated with a governance hardening entry.
- **No documentation gaps.**

### @Compliance — APPROVE

- Exception records provide SOC 2 audit evidence for justified deviations.
- The `Conditions` field ensures exceptions have documented re-evaluation triggers, preventing indefinite exemptions.
- The formal lifecycle (Accepted → Retired) provides a clear audit trail.
- **No compliance concerns.**

### @Observability — APPROVE

- The `the-team.mdc` fix ensures @Observability has correct, observability-specific responsibilities.
- No logging or tracing changes are part of this changeset.
- **No concerns.**

## Targeted Refactors & Cleanups (INFRA-043)

- [x] Merge `layer-boundaries.mdc` into `architectural-standards.mdc` to avoid duplication
- [x] Fix §6 @Observability copy-paste bug in `the-team.mdc`
- [ ] Audit remaining rules for universality (documented, deferred to future story)

## Implementation Steps

### ADR System

#### [NEW] `.agent/adrs/ADR-021-architectural-exception-records.md`
- Create ADR establishing `EXC-*` as a formal ADR subtype.
- Include: Context, Decision (format, naming, preflight integration, lifecycle), Alternatives, Consequences.

#### [NEW] `.agent/templates/exception-template.md`
- Create template with fields: Status, Challenged By, Rule Reference, Affected Files, Justification, Conditions, Consequences.

#### [NEW] `.agent/adrs/EXC-001-update-story-state-location.md`
- Convert existing ad-hoc rebuttal into formal exception record.
- Include full justification for `update_story_state` remaining in `commands/utils.py`.

#### [DELETE] `.agent/cache/rebuttals/2026-02-09-update-story-state-location.md`
- Remove ad-hoc rebuttal file.

---

### Governance Rules

#### [MODIFY] `.agent/rules/adr-standards.mdc`
- Add `## Exception Records (EXC-*)` section documenting the subtype, its prefix, template, storage, lifecycle, and preflight integration.

#### [MODIFY] `.agent/rules/architectural-standards.mdc`
- Merge content from `layer-boundaries.mdc`: general layer principle, IS/ISN'T violation sections, codebase-specific boundary map, enforcement language.
- Change glob from `.agent/src/**/*.py` to `**/*.py` and add `alwaysApply: true`.

#### [DELETE] `.agent/rules/layer-boundaries.mdc`
- Remove duplicate file after merge.

#### [NEW] `.agent/rules/breaking-changes.mdc`
- Define breaking vs non-breaking changes with concrete examples.
- Add 3-question verification checklist.
- Scope enforcement to @QA and @Architect.

---

### Preflight Workflow

#### [MODIFY] `.agent/workflows/preflight.md`
- Insert Step 3 (LOAD EXCEPTIONS) between LOAD RULES and ROLE REVIEWS.
- Renumber subsequent steps (VERDICTS → 5, OVERALL OUTCOME → 6).

---

### Team Roles

#### [MODIFY] `.agent/rules/the-team.mdc`
- Replace §6 @Observability (copy-paste of @Docs) with observability-specific responsibilities: structured logging, tracing, PII-safe logs, audit log entries.

## Verification Plan

### Automated Tests

- [ ] Existing unit test suite passes (no application logic changed)

### Manual Verification

- [ ] Run `/preflight` on a changeset touching `commands/utils.py` — verify EXC-001 suppresses the location challenge
- [ ] Run `/preflight` on a changeset with a genuine violation — verify it still BLOCKs
- [ ] Verify all new files are well-formed markdown with correct frontmatter

## Definition of Done

### Documentation

- [x] ADR-021 created and accepted
- [x] `adr-standards.mdc` updated
- [ ] CHANGELOG.md updated with governance hardening entry

### Observability

- [x] No logging changes (governance-layer only)
- [x] No metrics changes

### Testing

- [ ] Unit tests passed
- [ ] Manual preflight verification completed
