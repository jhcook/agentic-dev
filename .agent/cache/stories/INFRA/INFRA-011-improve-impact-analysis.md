# INFRA-011: Improve Impact Analysis

## Parent Plan
INFRA-008

## State
OPEN

## Problem Statement
The `agent impact` command's static analysis is very limited (only lists files). It prints "TBD" for workflows and risks. We can do better by parsing imports.

## User Story
As a reviewer, I want `agent impact` to tell me which other files depend on the changed files, so I can assess risk even without AI.

## Acceptance Criteria
- [ ] Static analysis parses Python `import` statements and JS `import/require`.
- [ ] Identifies files that import the changed files (reverse dependency lookup).
- [ ] Updates the "Impact Analysis Summary" to list these dependent components.

## Impact Analysis Summary
Components touched: `agent/commands/check.py`, `agent/core/utils.py`
Workflows affected: Preflight, Review.
Risks identified: Parsing might be slow on large repos.

## Test Strategy
- Create file A and file B (where B imports A).
- Modify A.
- Run `agent impact`.
- Verify B is listed as impacted.
