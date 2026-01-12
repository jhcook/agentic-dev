# INFRA-001: Smart AI Router and Python Rewrite

## Status
COMMITTED

## Problem Statement
The current agent architecture lacks intelligent model routing and relies on legacy dependencies. We need to implement a Smart AI Router to optimize cost and performance, and rewrite core components in Python for better maintainability.

## User Story
As a developer, I want the agent to automatically select the best AI model for a given task so that I can balance cost and quality without manual configuration.

## Acceptance Criteria
- [x] SmartRouter implementation selects models based on tier and context window.
- [x] TokenManager accurately counts tokens.
- [x] Legacy tests are updated and passing.
- [x] System uses `google-genai` SDK and `tiktoken`.

## Non-Functional Requirements
- Performance: Router decision must be <10ms.
- Reliability: Fallback to alternative providers if one fails.

## Impact Analysis Summary
- Replaces `agent/core/ai.py` logic.
- Requires new dependencies (`tiktoken`, `google-genai`).
- Updates CLI help text formatting.

## Test Strategy
- Unit tests for SmartRouter logic.
- Integration tests for `agent preflight`.
- Legacy test suite verification.

## Rollback Plan
- Revert commit `INFRA-001-smart-ai-router` branch.
- Downgrade dependencies in `pyproject.toml`.
