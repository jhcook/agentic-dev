# INFRA-117: Improve Implement Error Hints

## State

REVIEW_NEEDED

## Problem Statement

When the `agent implement` orchestrator executes a full-file replace (`[NEW]` or `[MODIFY]`), it uses a file size guard (INFRA-096) that rejects overwrites on files larger than `FILE_SIZE_GUARD_THRESHOLD` (200 lines). Currently, if this size constraint is breached, the rejected file drops into a generic catching block which blindly outputs: `Hint: update runbook step(s) to use <<<SEARCH/===/>>> blocks`. This generic hint actively gaslights users into attempting `SEARCH/REPLACE` for files that are genuinely `[NEW]` but that already coincidentally exist beyond the line threshold on disk (e.g. from an out-of-band commit or previous partial run). We need descriptive errors out of the `implement` gate that accurately distinguish between size constraint rejections, bad docstrings, idempotency problems, and generic parsing errors.

## User Story

As a Developer, I want descriptive, context-aware error messages when `agent implement` rejects a file change so that I know exactly why my implementation failed and do not receive misleading instructions to rewrite new files as search/replace blocks.

## Acceptance Criteria

- [ ] **AC-1**: Modify the file size guard in `core/implement/guards.py` to raise a specific `FileSizeGuardViolation` exception, rather than just returning `False`.
- [ ] **AC-2**: Modify the docstring guard to raise a `DocstringGuardViolation` with the violation details, or update the orchestrator to pass the specific docstring rejection reason through to the final summary.
- [ ] **AC-3**: Update the implement orchestrator (`core/implement/orchestrator.py`) to handle these distinct exceptions/responses and output an error summary that precisely explains the cause (e.g., "File exists and is > 200 LOC. Overwrite blocked.").
- [ ] **AC-4**: A `[NEW]` block matching a pre-existing file on disk should not suggest a search/replace unless it is explicitly an attempt to mutate an existing overgrown file.
- [ ] **AC-5**: Add unit tests in `tests/core/implement/` to simulate the size guard and formatting exception paths, verifying the exact output text of the hints.

## Non-Functional Requirements

- **Observability**: Maintain rich console output without clutter; ensure distinct telemetry traces for different rejection reasons.

## Linked ADRs

- ADR-041 (Module Size Limits)

## Linked Journeys

- JRN-088 (Console Agentic Tool Capabilities)
- JRN-096 (Safe Implementation Apply)

## Impact Analysis Summary

- Components touched: `agent/core/implement/guards.py`, `agent/core/implement/orchestrator.py`, `tests/core/implement/test_guards.py`, `tests/core/implement/test_orchestrator.py`
- Workflows affected: Runbook implementation phase.
- Risks identified: Changes to exception routing or return types may affect existing `agent implement` unit tests which currently expect a boolean return from `apply_change_to_file`.

## Test Strategy

- **Unit Tests**: Add tests to `tests/core/implement/` simulating specific rejection paths (e.g., `FileSizeGuardViolation`, `DocstringGuardViolation`).
- **Scenario Validation**: Assert that `[NEW]` and `[MODIFY]` blocks correctly parse size violations and docstring errors.
- **Output Assertion**: Verify the specific string output produced by the generic catching block to ensure the correct context-aware hint is presented.

## Rollback Plan

Revert the implement error propagation changes.

## Copyright

Copyright 2026 Justin Cook
