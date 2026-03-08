# INFRA-104: Decompose TUI Application

## State

COMMITTED

## Parent Plan

INFRA-099

## Problem Statement

The `tui/app.py` module has grown to 2,008 LOC — the largest file in the codebase — and combines three orthogonal concerns: the Textual `App` scaffold (layout, bindings, lifecycle), prompt/input handling (message composition, multi-turn history, slash command parsing), and the chat backend integration (streaming response display, provider orchestration, disconnect recovery). This makes any UI change a high-risk operation that could inadvertently affect backend streaming logic and vice versa.

## User Story

As a **Backend Engineer**, I want to **decompose the monolithic TUI app into a layout scaffold, a prompt-handling module, and a chat-integration module** so that **UI changes are isolated from streaming logic, each module stays within the 500 LOC ceiling, and the TUI is independently testable.**

## Acceptance Criteria

- [ ] **AC-1**: `tui/app.py` is reduced to the Textual `App` subclass, `compose()`, lifecycle hooks (`on_mount`, `on_unmount`), key bindings, and widget wiring — ≤500 LOC.
- [ ] **AC-2**: `tui/prompts.py` contains input handling: `InputType` resolution, slash command parsing, multi-turn history management, and message templating helpers.
- [ ] **AC-3**: `tui/chat.py` contains the chat backend integration: `SelectionLog`, streaming chunk rendering, provider handoff, disconnect recovery, and the `@work` async task workers.
- [ ] **AC-4**: All public symbols used by `tui/commands.py` and other importers remain accessible; update imports in dependent modules as needed.
- [ ] **AC-5**: All existing tests in `tests/tui/` pass without modification (behavioural equivalence).
- [ ] **AC-6**: No circular imports — `python -c "import agent.cli"` and `python -c "from agent.tui.app import ConsoleApp"` both succeed.
- [ ] **AC-7**: New unit tests in `tests/tui/test_prompts.py` and `tests/tui/test_chat.py` covering slash command parsing and streaming chunk rendering respectively.
- [ ] **AC-8**: All new modules include PEP-484 type hints and PEP-257 docstrings.
- [ ] **Negative Test**: Disconnect recovery in `chat.py` re-establishes the streaming connection without crashing the TUI when the provider raises a network error.

## Non-Functional Requirements

- **Performance**: TUI startup time and first-token latency unchanged.
- **Security**: No sensitive provider config or API keys logged via `RichLog` or `SelectionLog` — scrubbing preserved.
- **Compliance**: N/A.
- **Observability**: Async worker spans and structured logging preserved across the new module boundaries.

## Linked ADRs

- ADR-041: Module Decomposition Standards

## Linked Journeys

- JRN-072: Terminal Console TUI Chat
- JRN-035: Advanced Voice Orchestration

## Impact Analysis Summary

- **Components touched**: `tui/app.py` (refactor, thinned), `tui/prompts.py` (new), `tui/chat.py` (new).
- **Workflows affected**: `agent console` command, all TUI-driven journeys.
- **Risks identified**: The Textual `@work` decorator ties async workers to the `App` class — care needed when moving workers to `chat.py` to ensure they still have access to `self` (the App instance) via a passed reference or mixin pattern.

## Test Strategy

- **Regression**: Run existing `tests/tui/` suite without modification; 100% pass rate required.
- **Unit Testing**: New tests for prompt parsing (slash commands, multi-turn history truncation) and streaming chunk rendering (partial token assembly, error chunk handling).
- **Integration**: Launch `agent console` and verify multi-turn chat, slash commands, and disconnect recovery behave identically to pre-refactor.

## Rollback Plan

- Revert the feature branch to the previous stable commit on `main`.
- Restore `tui/app.py` from git history and remove `tui/prompts.py` and `tui/chat.py`.

## Copyright

Copyright 2026 Justin Cook
