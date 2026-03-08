# INFRA-111: Extract Prompt and Command Logic

## State

COMMITTED

## Parent Plan

INFRA-099

## Problem Statement

The `tui/app.py` monolith needs decomposition. We need to extract the prompt and command logic into a separate module `agent/tui/prompts.py` to isolate UI changes from streaming logic and improve testability.

## User Story

As a Backend Engineer, I want to create `agent/tui/prompts.py` and migrate all input-related logic including slash command parsing, history management, and input mode resolution, so that these concerns are isolated, keeping the module within the 500 LOC ceiling, and making it independently testable.

## Acceptance Criteria

- [ ] `InputType` enum and `CommandParser` class moved to `tui/prompts.py`.
- [ ] Logic for history truncation and multi-turn message templating migrated.
- [ ] Zero dependencies on Textual `App` or `Widget` instances (use pure data structures or interfaces).
- [ ] Unit tests in `tests/tui/test_prompts.py` for slash command parsing.

## Non-Functional Requirements

- **Performance**: N/A
- **Security**: N/A
- **Compliance**: N/A
- **Observability**: N/A

## Linked ADRs

- ADR-041: Module Decomposition Standards

## Linked Journeys

- JRN-072: Terminal Console TUI Chat
- JRN-035: Advanced Voice Orchestration

## Impact Analysis Summary

- **Components touched**: `tui/app.py`, `tui/prompts.py`
- **Workflows affected**: `agent console`
- **Risks identified**: N/A

## Test Strategy

- **Unit Testing**: Unit tests in `tests/tui/test_prompts.py` for slash command parsing.

## Rollback Plan

Revert to previous commit.

## Copyright

Copyright 2026 Justin Cook
