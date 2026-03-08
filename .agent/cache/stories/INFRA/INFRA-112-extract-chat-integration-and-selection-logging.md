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

## Copyright

Copyright 2026 Justin Cook
