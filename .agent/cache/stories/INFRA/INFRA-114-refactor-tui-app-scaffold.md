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
- [ ] All existing UI bindings (keys, buttons) remain functional.

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

- **Components touched**: `tui/app.py`
- **Workflows affected**: `agent console`
- **Risks identified**: Potential circular imports if `tui/app.py` references symbols from modules that depend on `app.py`.

## Test Strategy

- **Regression**: Run existing `tests/tui/` suite without modification; 100% pass rate required.

## Rollback Plan

Revert to previous commit.

## Copyright

Copyright 2026 Justin Cook
