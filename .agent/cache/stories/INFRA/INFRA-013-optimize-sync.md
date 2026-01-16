# INFRA-013: Optimize Sync for Large Datasets

## Parent Plan
INFRA-008

## State
OPEN

## Problem Statement
The `agent sync` command loads all artifacts into memory and does not handle pagination. This will fail with large datasets.

## User Story
As a user with a large repo, I want `agent sync` to handle thousands of artifacts without crashing.

## Acceptance Criteria
- [ ] `agent sync pull` uses pagination (limit/offset) when fetching from Supabase.
- [ ] `agent sync push` chunks uploads.

## Impact Analysis Summary
Components touched: `agent/sync/sync.py`
Workflows affected: Sync.
Risks identified: Data consistency during partial syncs.

## Test Strategy
- Mock a large number of artifacts (e.g. 1000).
- Run `agent sync`.
- Verify memory usage and success.
