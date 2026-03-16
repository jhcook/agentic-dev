# INFRA-151: Python Syntax Validation & Testing

## State

REVIEW_NEEDED

## Problem Statement

Current runbook validation only checks structural schema. Consequently, runbooks containing Python code blocks can pass validation while containing syntax errors, leading to failures during execution.

## User Story

As a **DevOps Engineer**, I want **automated Python syntax validation for runbook code blocks** so that **execution failures caused by malformed code are caught before deployment.**

## Acceptance Criteria

- [ ] **Scenario 1**: Given a runbook with a `[NEW]` block targeting a `.py` file, When the validation pipeline runs, Then the utility must use `ast.parse()` to verify syntax.
- [ ] **Scenario 2**: Python syntax errors must be logged to `stderr` as non-blocking warnings, allowing the pipeline to proceed while informing the user.
- [ ] **Negative Test**: System handles the following cases gracefully by reporting errors in `tests/test_runbook_validation.py`:
    - Missing code blocks in `[NEW]` tags.
    - Empty Search/Replace (S/R) content in `[MODIFY]` tags.
    - Malformed or invalid file paths.
    - Missing "Implementation Steps" section header.

## Non-Functional Requirements

- **Performance**: Syntax checking must add negligible overhead (<100ms per file).
- **Security**: Use `ast.parse` to ensure code is analyzed without being executed.
- **Compliance**: Validation logs must be retained in CI/CD history for audit purposes.
- **Observability**: Warnings must be clearly labeled in CI/CD output for easy developer discovery.

## Linked ADRs

- ADR-012: Runbook Validation Standards

## Linked Journeys

- JRN-004: Runbook Authoring and Deployment

## Impact Analysis Summary

- **Components touched**: Runbook Validation Engine, CI/CD Pipeline scripts.
- **Workflows affected**: Runbook linting and pre-deployment validation.
- **Risks identified**: Potential for "noisy" logs if non-Python content is mistakenly tagged as `.py`.

## Test Strategy

- Implement a comprehensive negative test suite in `tests/test_runbook_validation.py`.
- Unit test the `ast.parse()` utility with valid and invalid Python snippets.
- Integration test to ensure `stderr` warnings do not cause CI pipeline exit codes to fail.

## Rollback Plan

- Disable the syntax check utility via a configuration flag in the validation pipeline or revert the commit to the validation engine.

## Copyright

Copyright 2026 Justin Cook
