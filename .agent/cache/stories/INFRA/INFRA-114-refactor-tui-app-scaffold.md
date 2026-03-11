# INFRA-114: Refactor TUI App Scaffold

## State

COMMITTED

## Parent Plan

INFRA-099

## Problem Statement

After extracting core logic, `tui/app.py` must be refactored to act purely as the App scaffold, defining layout and wirings.

## User Story

As a Backend Engineer, I want to clean up `tui/app.py` to contain only the `App` subclass, layout definitions, global bindings, and event wiring, so its size is reduced to $\le$ 500 LOC and it focuses purely on UI orchestration.

## Acceptance Criteria

- [ ] `tui/app.py` size is reduced to $\le$ 500 LOC.
- [ ] All imports updated to reference `tui.prompts` and `tui.chat`.
- [ ] Circular import check: `python -c "from agent.tui.app import ConsoleApp"` succeeds.
- [ ] Critical UI bindings and user interactions remain functional as defined in JRN-072, including:
    - Initiating and starting a chat session.
    - Message submission (Enter) and real-time display.
    - Creating a new session/clearing context.
    - Graceful application exit.

## Non-Functional Requirements

- **Performance**: TUI startup time and first-token latency unchanged.
- **Security**: N/A
- **Compliance**: N/A
- **Observability**: N/A

## Linked ADRs

- ADR-041: Module Decomposition Standards

## Linked Journeys

- JRN-072: Terminal Console TUI Chat
- JRN-035: Advanced Voice Orchestration

## Impact Analysis Summary

- **Components touched**: `tui/app.py`, `tui/prompts.py`, `tui/chat.py`.
- **Workflows affected**: `agent console`
- **Risks identified**: Potential circular imports if `tui/app.py` references symbols from modules that depend on `app.py`.

## Test Strategy

- **Regression**: Run existing `tests/tui/` suite without modification; 100% pass rate required.
- **UI Binding Verification**: Perform a manual walkthrough of JRN-072 to ensure all hotkeys and button event handlers in the refactored scaffold correctly trigger logic now residing in `tui.prompts` and `tui.chat`.
- **Integration Testing**: Validate that the `ConsoleApp` correctly orchestrates the lifecycle of the newly separated sub-modules without introducing state synchronization errors or event loop blockages.

## Rollback Plan

Revert to previous commit.

## Copyright

Copyright 2026 Justin Cook