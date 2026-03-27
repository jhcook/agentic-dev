# INFRA-171: Consolidate Colocated Tests to .agent/tests and Enforce src/tests Separation

## State

DRAFT

## Problem Statement

Currently, 49 test files are fragmented across colocated `tests/` directories within `.agent/src/` (e.g., `.agent/src/agent/commands/tests/`). Because `.agent/pyproject.toml` sets `norecursedirs=["src"]`, these tests are orphaned and never executed by the CI/CD pipeline. This violates the project's architectural standard of separating source code from test code and leads to silent regressions.

## User Story

As a developer, I want all test files consolidated into the canonical `.agent/tests/` directory so that they are properly discovered by the test runner and maintain a clean separation between production logic and verification code.

## Acceptance Criteria

- [ ] **Scenario 1**: Migrating existing tests. Given the 49 orphaned test files in `.agent/src/`, when the migration script runs, then all files must be moved to `.agent/tests/` mirroring their original source hierarchy (e.g., `.agent/src/agent/core/ai/tests/test_logic.py` moves to `.agent/tests/agent/core/ai/test_logic.py`).
- [ ] **Scenario 2**: Enforcing the standard. The file `.agent/rules/400-lean-code.mdc` must contain a specific instruction forbidding the creation of `tests/` directories inside any `src/` directory.
- [ ] **Scenario 3**: Automated Generation. Runbook and code generation prompts must be updated to ensure any generated tests are placed in `.agent/tests/` or equivalent top-level test directories for other managed components (e.g., `backend/tests/`).
- [ ] **Negative Test**: If a developer attempts to create a test in `.agent/src/agent/core/`, the linting/rule system should flag a violation.

## Non-Functional Requirements

- **Maintainability**: Standardizes the directory structure across all repositories (Agent, Backend, etc.).
- **Observability**: Ensures 100% of written tests are visible to `pytest` and reported in coverage metrics.
- **Compliance**: Follows established Python project structure best practices.

## Linked ADRs

- ADR-012: Standardized Repository Structure

## Linked Journeys

- JRN-001: Developer Onboarding and Local Development

## Impact Analysis Summary

Components touched:
- `.agent/src/agent/commands/tests/` (and all other colocated test subdirectories)
- `.agent/tests/`
- `.agent/rules/400-lean-code.mdc`
- `.agent/pyproject.toml`
- `.agent/src/agent/core/ai/prompts.py` (runbook generation prompts)
- `backend/src/` (alignment check)
- `backend/tests/` (alignment check)

Workflows affected:
- Local unit testing via `pytest`
- CI/CD Test execution pipelines
- Automated code generation via LLM prompts

Risks identified:
- Broken imports in migrated test files (e.g., relative imports like `from ..module import X` may need adjustment to absolute imports).

## Test Strategy

1.  **Baseline**: Run `pytest` and record the number of tests executed.
2.  **Migration**: Move the 49 files and update import statements.
3.  **Verification**: Run `pytest` again. The number of tests executed should increase by exactly the number of migrated files (minus any previously discovered tests).
4.  **Rule Check**: Manually trigger a Cursor rule check to ensure `.agent/rules/400-lean-code.mdc` correctly identifies a colocated test directory as an error.

## Rollback Plan

1.  Revert the file moves using Git: `git checkout HEAD .agent/src/ .agent/tests/`.
2.  Revert changes to `.cursor/rules/400-lean-code.mdc` and prompt files.
3.  Ensure `pyproject.toml` remains in its original state to avoid running orphaned tests if imports are broken.

## Copyright

Copyright 2026 Justin Cook