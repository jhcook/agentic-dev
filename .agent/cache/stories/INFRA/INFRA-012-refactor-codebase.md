# INFRA-012: Refactor Codebase Utilities

## Parent Plan
INFRA-008

## State
OPEN

## Problem Statement
There is code duplication in the agent CLI, specifically around finding story files (`check.py` vs `runbook.py`). This makes maintenance harder.

## User Story
As a maintainer, I want common logic like `find_story_file` to be in `agent.core.utils` so I can reuse it.

## Acceptance Criteria
- [ ] `find_story_file` is moved/consolidated in `agent/core/utils.py`.
- [ ] `check.py` is updated to import and use the utility.
- [ ] Any other obvious duplication (e.g. `scrub_sensitive_data` usage patterns) is reviewed.

## Impact Analysis Summary
Components touched: `agent/commands/*.py`, `agent/core/utils.py`
Workflows affected: None (internal refactor).
Risks identified: Regressions in identifying files.

## Test Strategy
- Run `agent preflight` and `agent runbook` to verify they still find files correctly.
