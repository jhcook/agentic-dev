# INFRA-113: Migrate Async Task Workers and Recovery

## State

COMMITTED

## Parent Plan

INFRA-099

## Problem Statement

The async task workers and recovery logic are tightly coupled to the Textual `App` in `tui/app.py`. They need to be migrated to `chat.py`.

## User Story

As a Backend Engineer, I want to relocate the `@work` async tasks from `app.py` to `chat.py` so that stream handling is decoupled from the main UI layout, while properly implementing a Mixin or controller pattern to retain message loop access.

## Acceptance Criteria

- [ ] All `@work` decorated methods moved to a `ChatWorkerMixin` or a dedicated controller in `tui/chat.py`.
- [ ] Disconnect recovery logic (re-establishing streams) implemented in the new module.
- [ ] `app.py` utilizes the migrated workers via inheritance or delegation.
- [ ] Log scrubbing logic for sensitive keys is preserved during the move.

## Non-Functional Requirements

- **Performance**: N/A
- **Security**: Log scrubbing preserved.
- **Compliance**: N/A
- **Observability**: Async worker spans and structured logging preserved across the new module boundaries.

## Linked ADRs

- ADR-041: Module Decomposition Standards

## Linked Journeys

- JRN-072: Terminal Console TUI Chat
- JRN-035: Advanced Voice Orchestration

## Impact Analysis Summary

- **Components touched**: `tui/app.py`, `tui/chat.py`
- **Workflows affected**: `agent console`
- **Risks identified**: The Textual `@work` decorator ties async workers to the App class — care needed when moving workers to `chat.py` to ensure they still have access to `self` (the App instance) via a passed reference or mixin pattern.

## Test Strategy

- **Unit Testing**: 
  - Unit tests covering streaming chunk rendering and disconnect recovery.
  - Explicit verification testing that log scrubbing logic for sensitive keys is successfully preserved and actively sanitizing inputs.
- **Manual Verification**: 
  - "Negative Test" (disconnect recovery) in a live terminal session.
  - Inspection of logs and OpenTelemetry spans during streaming to ensure structured logging flows correctly across the new boundaries without leaking sensitive data.

## Rollback Plan

Revert to previous commit.

## Copyright

Copyright 2026 Justin Cook