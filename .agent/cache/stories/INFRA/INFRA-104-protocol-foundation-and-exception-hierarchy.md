# INFRA-104: Protocol Foundation and Exception Hierarchy

## State

COMMITTED

## Parent Plan

INFRA-099

## Problem Statement

The `providers.py` module is a monolithic dispatch file. Before we can port providers, we must update `protocols.py` to support runtime checking and establish the common exception hierarchy required by all concrete implementations, ensuring standardized error mapping across the board.

## User Story

As a Backend Engineer, I want the `AIProvider` protocol to be runtime checkable and include a common exception hierarchy so all concrete implementations conform to a standard contract.

## Acceptance Criteria

- [ ] **AC-1**: Update `AIProvider` in `core/ai/protocols.py` with `@runtime_checkable` decorator.
- [ ] **AC-2**: Implement new base exception classes: `AIProviderError`, `AIRateLimitError`, `AIAuthenticationError`, `AIInvalidRequestError` in `protocols.py` or a dedicated module.
- [ ] **AC-3**: Create `core/ai/providers/utils.py` with shared formatting and PII scrubbing helpers to reduce LOC redundancy in future providers.
- [ ] **AC-4**: Static tests (mypy) and unit tests for the exceptions run successfully.

## Non-Functional Requirements

- Performance: Exception resolution is lightweight.
- Observability: Exceptions must cleanly wrap underlying vendor API errors.

## Linked ADRs

- ADR-041

## Linked Journeys

- JRN-072
- JRN-023

## Impact Analysis Summary

Components touched: `core/ai/protocols.py`, `core/ai/providers/utils.py` (new)
Workflows affected: Preparatory for all core AI services.
Risks identified: Ensure `isinstance({}, AIProvider)` still functions as expected once `runtime_checkable` is added.

## Test Strategy

Unit tests to ensure exceptions subclass properly and can carry standard metadata (like `retry_after` properties).

## Rollback Plan

Revert the PR.

## Copyright

Copyright 2026 Justin Cook
