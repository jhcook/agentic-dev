# INFRA-055: Automated Branching for Implement Command

## State

ACCEPTED

## Goal Description

Enhance `agent implement` to automatically handle git branching. It should ensure the user starts from `main`, enforce a clean working state, and create a standard feature branch (`STORY-ID/synopsis`) before applying any changes.

## Panel Review Findings

- **@Architect**: Approved. Ensure `create_branch` distinguishes "exists" vs "create". Use `subprocess.run` safety.
- **@Security**: Approved. Sanitize inputs to prevent shell injection.
- **@QA**: Approved. Add specific test case for "User is on wrong story branch".
- **@Product**: Approved. Ensure descriptive error messages for blocking states.
- **@Observability**: Log "Branch Switch" events to `.agent/logs/implement.log`.

## Targeted Refactors & Cleanups (INFRA-043)

- None

## Implementation Steps

### Agent Core

#### [MODIFY] .agent/src/agent/commands/implement.py

- Import `subprocess` and git utilities.
- Add helper functions:
  - `get_current_branch()`
  - `is_git_dirty()`
  - `create_branch(story_id, title)` -> Should handle `git checkout` if exists, else `git checkout -b`.
  - `sanitize_branch_name(name)` -> Ensure no special chars/spaces.
- In `implement` function (before Phase 0):
  - Check git dirty state. Warn/Exit if dirty.
  - Check current branch.
  - Fetch Story title and ID.
  - Expected branch prefix: `STORY-ID/`.
  - If current branch matches `STORY-ID/*`:
    - Log "Already on story branch X, proceeding."
  - Elif current branch is `main`:
    - Generate branch name: `STORY-ID/sanitized-title`.
    - Create and/or Checkout branch (handle existence).
    - Log branch switch/creation event.
  - Else:
    - Warn "❌ You are on branch X. Please checkout main or the specific story branch to proceed."
    - Exit.

## Verification Plan

### Automated Tests

- [ ] Run `pytest .agent/tests/commands/test_implement.py`
- [ ] Add `test_implement_branching` to `test_implement.py`:
  - Mock `main` branch -> Success (creates new).
  - Mock `STORY-ID/existing` -> Success (stays).
  - Mock `OTHER-ID/existing` -> Fail (wrong story).
  - Mock `random-branch` -> Fail.
  - Mock dirty state -> Fail.

### Manual Verification

- [ ] Checkout `main`.
- [ ] Run `agent implement INFRA-055`--apply`.
- [ ] Verify `INFRA-055/...` is created.
- [ ] Switch back to `main`. Run again. Verify it switches back to `INFRA-055/...`.
- [ ] Modify a file. Run again. Verify it blocks.

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated

### Observability

- [ ] Logs show branch creation/checkout events.

### Testing

- [ ] Unit tests passed
