# INFRA-116: Fix targeted context hallucinations in runbook template

## State

COMMITTED

## Problem Statement

The runbook generation process provides the AI with limited context (only function signatures), leading to "hallucinations" where the AI fabricates implementation details. Additionally, the system lacks robust file handling and error management for missing context files.

## User Story

As a **DevOps Engineer**, I want **the AI to receive full file content and robust error handling** so that **generated runbooks are accurate, grounded in actual code, and resilient to missing files.**

## Acceptance Criteria

- [ ] **AC-1**: Given a runbook generation request, When the system processes `runbook.py` and `context.py`, Then it must pass the full file content to the AI prompt instead of only function signatures for targeted files.
- [ ] **AC-2**: All file I/O operations in these modules must use context managers (`with` statements) to ensure proper resource handling.
- [ ] **AC-3**: System handles `FileNotFoundError` gracefully by logging the error and returning a `FILE NOT FOUND (verify path!)` message, preventing the AI from hallucinating missing context.
- [ ] **AC-4**: The `runbook-template.md` must be updated to use the `Targeted File Contents` heading instead of `Target File Signatures`.

## Non-Functional Requirements

- **Performance**: Monitor token usage increase as full file contents replace signatures. (Mitigated by hardcoded truncated files limit).
- **Observability**: Log explicit errors when files are missing or unreadable.

## Linked ADRs

- ADR-025

## Linked Journeys

- JRN-089

## Impact Analysis Summary

**Components touched**: `context.py`, `runbook-template.md`, `runbook.py`, `test_infra_107.py`.
**Files Changed**: 4
**Blast Radius**: Low — additive changes to context loader.
**Risks identified**: Potential to exceed LLM context window limits if files are exceptionally large.

## Test Strategy

- **Unit Testing**: Tests updated in `test_infra_107.py` including happy paths, file-not-found error cases, and a new edge case test assuring truncation for files >30k characters.

## Rollback Plan

- Revert changes to `context.py` using Git revert to restore signature-only logic.

## Copyright

Copyright 2026 Justin Cook