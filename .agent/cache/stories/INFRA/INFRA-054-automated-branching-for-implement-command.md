# INFRA-054: Automated Branching for Implement Command

## State

COMMITTED

## Problem Statement

Currently, developers have to manually create and checkout branches before running `agent implement`. This adds friction and increases the risk of working on the wrong branch (e.g., directly on `main`).

## User Story

As a developer, I want `agent implement` to handle branching automatically, so that I can focus on the runbook content without worrying about git hygiene.

## Acceptance Criteria

- [ ] **Scenario 1**: When running `agent implement`, if current branch is not `main`, check if it matches `STORY-ID/matches-current-story`. The STORY-ID must match the STORY-ID of the story being implemented.
- [ ] **Scenario 2**: If on `main`, create and checkout `STORY-ID/sanitized-title`.
- [ ] **Scenario 3**: If on correct story branch, proceed.
- [ ] **Scenario 4**: If on incorrect branch (not main, not story), stop and notify user.
- [ ] **Scenario 5**: If git state is dirty, stop and notify user.

## Non-Functional Requirements

- Performance: Git operations should be fast and not delay the command significantly.
- Hygiene: Do not leave the repo in a detached head state.

## Linked ADRs

- None

## Linked Journeys

- JRN-013 (AI Provider Selection and Validation)

## Impact Analysis Summary

Components touched: `agent/commands/implement.py`
Workflows affected: `implement`
Risks identified: Potential for git conflicts if branch already exists (should handle gracefully).

## Test Strategy

- Unit tests mocking git subprocess.
- Manual verification by running against this very story.

## Rollback Plan

- Revert changes to `agent/commands/implement.py`.
