# INFRA-111: Extract Prompt and Command Logic

## State

IN_PROGRESS

## Parent Plan

INFRA-099

## Problem Statement

The `tui/app.py` monolith needs decomposition. We need to extract the prompt building logic into a separate module `agent/tui/prompts.py` to isolate UI changes from prompt building and improve maintainability.

## User Story

As a Backend Engineer, I want to create `agent/tui/prompts.py` and migrate all input-related logic including slash command parsing, history management, and input mode resolution, so that these concerns are isolated, keeping the module within the 500 LOC ceiling, and making it independently testable.

## Acceptance Criteria

- [ ] `_build_clinical_prompt`, `_build_custom_prompt`, and `_build_system_prompt` moved to `tui/prompts.py`.
- [ ] Logic for history truncation and multi-turn message templating migrated.
- [ ] Zero dependencies on Textual `App` or `Widget` instances (use pure data structures or interfaces).

## Non-Functional Requirements

- **Performance**: N/A
- **Security**: N/A
- **Compliance**: N/A
- **Observability**: N/A

## Linked ADRs

- ADR-041: Module Decomposition Standards

## Linked Journeys

- JRN-072: Terminal Console TUI Chat
- JRN-035: Restore Silero VAD with WebRTC Fallback

## Impact Analysis Summary

- **Components touched**: `tui/app.py`, `tui/prompts.py`
- **Workflows affected**: `agent console`
- **Risks identified**: N/A

## Test Strategy

- **Unit Testing**: N/A for this structural move.

## Rollback Plan

Revert to previous commit.

## Copyright

Copyright 2026 Justin Cook
