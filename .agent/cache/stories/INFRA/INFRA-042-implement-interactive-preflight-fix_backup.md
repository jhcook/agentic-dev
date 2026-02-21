# INFRA-042: Implement Interactive Preflight Repair

## State

COMMITTED

## Problem Statement

When `env -u VIRTUAL_ENV uv run agent preflight` fails (e.g., due to invalid Story schema, linting errors, or test failures), the user is presented with an error message and must manually investigate, edit files, and re-run the command. This context switching is inefficient. Users want the Agent to not only detect issues but also analyze them and propose specific, actionable fixes that can be applied immediately and verified.

## User Story

As a Developer, I want an interactive "fix" mode for the `env -u VIRTUAL_ENV uv run agent preflight` command (e.g., `env -u VIRTUAL_ENV uv run agent preflight --interactive`) that identifies blocking issues, presents me with AI-generated options to resolve them, and automatically verifies the chosen fix against the test suite, so that I can resolve governance blockers rapidly without leaving the terminal.

## Acceptance Criteria

- [ ] **CLI Command**: Add a `--interactive` flag to `env -u VIRTUAL_ENV uv run agent preflight`.
- [ ] **Architecture**: Implement `InteractiveFixer` as a standalone, reusable service in `agent.core.fixer` (decoupled from CLI).
- [ ] **Analysis Engine**: Implement logic to capture failure details from:
  - Story Schema Validation (missing sections, headers).
  - Linter checks (if implemented in preflight).
  - Unit Checks (test failures).
- [ ] **Proposal Generation**: Use the AI Service to generate 1-3 distinct solution options for each failure.
  - Example: "Option 1: Add missing 'Impact Analysis' section with placeholder."
  - Example: "Option 2: Generate 'Impact Analysis' based on git diff."
- [ ] **Interactive UI**: Use `rich` or `questionary` to present options to the user.
- [ ] **Verification Loop**:
  - Apply selected fix.
  - Re-run the specific check that failed.
  - If pass -> Continue.
  - If fail -> Offer retry or revert.
- [ ] **Safety**:
  - Mandatory "Diff View" before applying any AI change.
  - Use `git stash` (or similar safe revert mechanism) to ensure failed repairs can be rolled back cleanly.

## Non-Functional Requirements

- **Transparency**: The user must always explicitly approve a change (Human-in-the-loop).
- **Resilience**: The tool handles failed fixes gracefully by reverting to the previous state.

## Impact Analysis Summary

- **Components**: `agent/commands/check.py`, `agent/core/ai`, `agent/core/utils.py`.
- **Risks**: AI generating incorrect code. Mitigated by "Verification Loop" and "Diff" view.

## Test Strategy

- **Unit**:
  - Mock the AI service to return preset options.
  - Verify that option selection applies the correct file edit.
  - Verify that successful re-check clears the error.
- **Manual**:
  - Corrupt a story file (remove section). Run `env -u VIRTUAL_ENV uv run agent fix`. Verify prompt and repair.
  - Break a test. Run `env -u VIRTUAL_ENV uv run agent fix`. Verify prompt and repair (assuming AI can fix simple logic).

## Rollback Plan

- Revert changes to `agent/commands/check.py` and delete `agent/core/fixer.py`.
- Remove `InteractiveFixer` references from any other tools.
