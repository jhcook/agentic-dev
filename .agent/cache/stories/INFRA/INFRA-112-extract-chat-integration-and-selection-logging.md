# INFRA-112: Extract Chat Integration and Selection Logging

## State

COMMITTED

## Parent Plan

INFRA-099

## Problem Statement

The `tui/app.py` monolith needs decomposition. We need to extract the chat backend integration and selection logging into a separate module `agent/tui/chat.py`.

## User Story

As a Backend Engineer, I want to create `agent/tui/chat.py` to house the `SelectionLog` and the core streaming response processing logic, so that UI changes are isolated from streaming logic.

## Acceptance Criteria

- [ ] `SelectionLog` class moved to `tui/chat.py`.
- [ ] Streaming chunk assembly and error chunk processing logic migrated.
- [ ] Provider handoff logic (selecting which backend to call) moved.
- [ ] Public interface defined for `app.py` to push chunks to the chat module.

## Non-Functional Requirements

- **Performance**: N/A
- **Security**: No sensitive provider config or API keys logged via `SelectionLog` — scrubbing preserved.
- **Compliance**: N/A
- **Observability**: N/A

## Linked ADRs

- ADR-041: Module Decomposition Standards

## Linked Journeys

- JRN-072: Terminal Console TUI Chat
- JRN-035: Advanced Voice Orchestration

## Impact Analysis Summary

- **Components touched**: `tui/app.py`, `tui/chat.py`
- **Workflows affected**: `agent console`
- **Risks identified**: N/A

## Test Strategy

- **Regression**: Run existing `tests/tui/` suite without modification.
- **Integration**: Launch `agent console` and verify.

## Rollback Plan

Revert to previous commit.

## Panel Consultation Advice

### @Architect
- Ensure `tui/chat.py` does not import UI execution logic back from `app.py` to avoid circular dependencies.
- Define a strict, decoupled "public" interface for `app.py` to use (e.g., a structured event payload), keeping internal chunk parsing private to `chat.py`.

### @Security
- Verify that the test coverage for secret scrubbing (`tests/tui/`) is comprehensive before moving the logic.
- Ensure any new logging introduced around the provider handoff logic continues to mask API keys and potentially sensitive provider configurations.

### @QA
- Add specific unit tests for `tui/chat.py` to validate chunk assembly mechanisms independently of the UI.
- Mock the provider handoff logic in isolation to confirm error chunk processing behaves correctly under simulated failure conditions.

### @Product
- Double-check that "Public interface defined for app.py to push chunks" fully covers the desired integration before executing the code changes.

### @Backend
- Leverage Python's `asyncio` generators (`async def yield_chunks()`) to represent the stream if not already doing so.
- Explicitly type the new public interface in `tui/chat.py` using Python type hints to ensure `app.py` interacts with it.

### @Observability
- Consider adding structured `.debug()` or `.info()` logs when the provider handoff occurs to make debugging context clearer.
- Maintain existing structured logging formats so current dashboards remain intact.

## Copyright

Copyright 2026 Justin Cook
