# INFRA-107: Harden Runbook Generation with Targeted Codebase Introspection

## State

COMMITTED

## Problem Statement

INFRA-066 added source code context (file tree + snippets) to `agent new-runbook`, but INFRA-100's implementation exposed three critical gaps that caused the generated runbook to contain aspirational code that didn't match the actual codebase:

1. **Budget truncation**: `_load_source_snippets()` has an 8000 char budget and loads files alphabetically. For 50+ source files, the target module (e.g., `core/ai/service.py`) may be truncated or excluded entirely.
2. **Tests excluded**: `exclude_dirs = {"tests"}` means the AI has zero visibility into existing `patch()` targets. When the runbook proposes moving functions between modules, it cannot warn about mock breakage.
3. **No story-targeted loading**: A refactoring story about `service.py` gets the same generic snippets as any other story. There is no mechanism to prioritize files explicitly referenced in the story.

These gaps caused INFRA-100's runbook to:
- Propose `async def` signatures when the codebase uses sync
- Propose a `providers/` package when the convention is flat modules
- Ignore 15+ test files that needed mock/patch migration
- Miss a `auto_fallback=True` default that was silently changed

With these fixes, `agent panel` becomes redundant for design review because the runbook is born source-code-aware. Panel can be deprecated to ad-hoc Q&A only.

## User Story

As a developer running `agent new-runbook`, I want the generated runbook to include full signatures of referenced files, a test impact matrix of mock/patch targets, and behavioral contracts from existing tests, so that the implementation plan is grounded in actual codebase state and does not produce broken code.

## Acceptance Criteria

- [ ] **AC-1: Targeted Context**: Given a story that references files via `#### [MODIFY] path/to/file.py`, when `new-runbook` is invoked, then the AI prompt includes full function/class signatures for each referenced file (unlimited budget for targeted files).
- [ ] **AC-2: File Not Found Warning**: Given a story that references a file path that does not exist, then the targeted context includes a `FILE NOT FOUND (verify path!)` warning for that path.
- [ ] **AC-3: Test Impact Matrix**: Given a story referencing module `agent.core.ai.service`, when `new-runbook` is invoked, then the AI prompt includes a list of all test files containing `patch("agent.core.ai.service.*")` targets, with the specific patch strings.
- [ ] **AC-4: Behavioral Contracts**: Given a story touching a module, when `new-runbook` is invoked, then the AI prompt includes default parameter values and key assertions extracted from existing tests for that module.
- [ ] **AC-5: Template Sections**: The `runbook-template.md` includes mandatory `## Codebase Introspection` and `## Test Impact Matrix` sections that the AI must fill with data from the injected context.
- [ ] **AC-6: System Prompt Update**: The system prompt instructs the AI: "You MUST copy actual signatures from TARGETED FILE SIGNATURES. You MUST list all patch targets from TEST IMPACT MATRIX in the runbook."
- [ ] **AC-7: Backward Compatibility**: If no targeted files are found or tests directory is missing, the runbook generation completes successfully with existing context only.
- [ ] **AC-8: Performance**: Combined targeted context loading adds < 1 second to generation time.

## Non-Functional Requirements

- **Security**: All loaded content passes through `scrub_sensitive_data()`.
- **Compliance**: No secrets or PII in injected context.
- **Observability**: Log targeted context size, test impact count, and behavioral contract count at DEBUG level.

## Linked Stories

- INFRA-066: Add Source Code Context to Runbook Generation (predecessor — this extends it)
- INFRA-100: Decompose AI Service Module (lesson learned — this story prevents recurrence)

## Linked ADRs

- ADR-025: Lazy initialization pattern
- ADR-041: Module Decomposition Standards

## Linked Journeys

- JRN-089: Generate Runbook with Targeted Codebase Introspection

## Impact Analysis Summary

**Components**: `context.py`, `runbook.py`, `runbook-template.md`
**Files Changed**: 3
**Blast Radius**: 🟢 Low — additive changes to context loader and runbook generation prompt
**Risks**: Additional context could push token limits for smaller providers (mitigated by AC-3 configurable budget)

## Test Strategy

- **Unit test**: `_load_targeted_context()` returns signatures for files referenced in story content.
- **Unit test**: `_load_targeted_context()` returns `FILE NOT FOUND` for nonexistent paths.
- **Unit test**: `_load_test_impact()` finds `patch()` targets in test files matching story modules.
- **Unit test**: `_load_behavioral_contracts()` extracts default values from test assertions.
- **Unit test**: All three functions gracefully return empty strings when directories are missing.
- **Integration test**: Generated runbook includes `## Codebase Introspection` and `## Test Impact Matrix` sections.

## Rollback Plan

Revert changes to `context.py`, `runbook.py`, and `runbook-template.md`. The feature is additive — removing the targeted context restores INFRA-066 behavior.

## Copyright

Copyright 2026 Justin Cook
