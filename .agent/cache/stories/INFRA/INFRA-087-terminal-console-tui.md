# INFRA-087: Terminal Console TUI

## State

DRAFT

## Problem Statement

Developers working in SSH-only or terminal-only environments have no interactive way to manage the agent through conversation. The existing `agent query` is single-shot and stateless — it cannot maintain conversation context, select workflows/roles, or cache tokens. More critically, the current workflow execution model requires separate CLI invocations for each action. A conversational interface would allow developers to chain workflow actions within a persistent context, dramatically improving productivity — the same way tools like Antigravity and Cursor provide in GUI environments.

The core value proposition is **conversation-driven agent management**: rather than invoking `agent implement INFRA-087`, `agent preflight`, `agent commit` as separate disconnected commands, the developer can carry context across a session — `/implement INFRA-087`, review the output, ask follow-up questions, then `/preflight` and `/commit` — all within a single conversation that accumulates understanding.

## User Story

As a developer with terminal access, I want an interactive console UI (`agent console`) so that I can manage the agent through persistent, multi-turn conversations, invoke workflows and roles in-context, switch AI providers, and benefit from token caching — providing the same conversational productivity as GUI-based AI tools.

## Acceptance Criteria

### Core Chat Experience
- [ ] **AC-01 – Launch**: Given the user runs `agent console` (or `agent console --provider <provider>` for a non-default provider), When the TUI loads, Then a split-pane layout appears with: chat output (top-left), input box (bottom), workflow list (top-right), and role list (bottom-right), using the specified (or default) provider.
- [ ] **AC-02 – Streaming Chat**: Given the user types a message and presses Enter, When the AI responds, Then the response streams token-by-token into the chat output pane with markdown rendering.
- [ ] **AC-03 – Persistent Conversation**: Given an active conversation, When the user sends multiple messages, Then conversation history is maintained and previous turns are sent as context (within the token budget) to the AI.
- [ ] **AC-04 – Token Caching**: Given a conversation with accumulated history, When the token count exceeds the configured budget, Then oldest turns are pruned FIFO while preserving the system prompt and most recent turns.
- [ ] **AC-05 – Resume**: Given a previously saved conversation, When the user runs `agent console`, Then the most recent conversation is automatically resumed with full history.

### Workflow & Role Integration
- [ ] **AC-06 – Workflow Selection (Sidebar)**: Given the user presses Tab to focus the workflow panel and uses arrow keys, When they press Enter on a workflow (e.g., `/commit`), Then the workflow name is inserted into the input box prefixed with `/`.
- [ ] **AC-07 – Role Selection (Sidebar)**: Given the user presses Tab to focus the role panel and uses arrow keys, When they press Enter on a role (e.g., `@architect`), Then the role name is inserted into the input box prefixed with `@`.
- [ ] **AC-08 – Workflow Invocation**: Given the user sends `/implement describe the API`, When the message is submitted, Then the workflow instructions from `workflows/implement.md` are loaded into the system prompt context and the user's message is processed with that context.
- [ ] **AC-09 – Role Invocation**: Given the user sends `@security review the auth module`, When the message is submitted, Then the role persona, responsibilities, and governance checks from `agents.yaml` are loaded into the system prompt context.
- [ ] **AC-10 – Contextual Workflow Chaining**: Given the user has already discussed a topic, When they invoke `/preflight` as a follow-up, Then the workflow executes with awareness of the prior conversation context.

### Multi-Provider Support
- [ ] **AC-11 – Provider at Launch**: Given the user runs `agent console --provider anthropic`, When the TUI loads, Then the session uses Anthropic as the AI provider (consistent with the `--provider` flag on all other agent commands).
- [ ] **AC-12 – Provider Switch Mid-Session**: Given the console is running, When the user types `/provider vertex`, Then the active AI provider switches to vertex and a confirmation is displayed. Typing `/provider` with no argument shows the current provider and all available providers with their status.
- [ ] **AC-13 – Model Selection**: Given the console is running, When the user types `/model gemini-2.5-pro`, Then subsequent AI calls use the specified model override.
- [ ] **AC-14 – Provider Consistency**: Given no explicit model override is set, When a message is sent, Then `stream_complete()` uses the same provider selection and model resolution logic as `complete()`, ensuring consistent behaviour across all agent commands.

### Conversation Management
- [ ] **AC-15 – New Conversation**: Given an active conversation, When the user types `/new`, Then a new empty conversation is created and becomes active with a fresh system prompt.
- [ ] **AC-16 – List Conversations**: Given multiple saved conversations exist, When the user types `/conversations`, Then a selectable list of past conversations is shown with timestamps and preview text.
- [ ] **AC-17 – Switch Conversation**: Given the numbered conversation list is displayed via `/conversations`, When the user types `/switch <n>`, Then the selected conversation becomes active with its full history restored.
- [ ] **AC-18 – Delete Conversation**: Given saved conversations exist, When the user types `/delete` (or `/delete <n>`), Then the specified (or current) conversation is deleted after the system prompts for confirmation.
- [ ] **AC-19 – Conversation Title**: Conversations are automatically titled based on the first user message (or can be renamed with `/rename <title>`).

### Console Commands
- [ ] **AC-20 – Help**: Given the console is running, When the user types `/help`, Then all available commands are listed with descriptions.
- [ ] **AC-21 – Quit**: Given the console is running, When the user types `/quit`, Then the TUI exits cleanly and the conversation state is persisted.
- [ ] **AC-22 – Clear**: Given the console is running, When the user types `/clear`, Then the chat output pane is cleared but the conversation history is preserved in the backend.

### Error Handling
- [ ] **AC-23 – No Provider**: Given no AI provider is configured, When the user launches `agent console`, Then an error message displays which providers were attempted and how to configure them.
- [ ] **AC-24 – Provider Failure**: Given the active provider fails mid-conversation, When the failure is detected, Then a modal dialog appears offering the user options to 'Retry', 'Switch Provider', or 'Cancel'.

## Non-Functional Requirements

- Performance: TUI startup in under 2 seconds. Streaming response latency matches raw API latency (no buffering overhead).
- Security: Conversation history stored locally in `.agent/cache/console.db` (SQLite, `0600` permissions). No conversation data transmitted except to configured AI providers.
- Compliance: License headers on all new source files. Conversations stored alongside existing `agent.db`.
- Observability: Structured logging for session lifecycle events (start, end, conversation switch). OpenTelemetry span for each AI completion within the console.

## Linked ADRs

- ADR-025 (Lazy Initialization)
- ADR-028 (Synchronous CLI)
- ADR-039 (Terminal Console TUI)

## Linked Journeys

- JRN-072 (Terminal Console TUI Chat)

## Impact Analysis Summary

Components touched: New `agent/tui/` package (`app.py`, `commands.py`, `session.py`, `styles.tcss`), new `agent/commands/console.py`, CLI registration in `agent/main.py`, new `stream_complete()` method on `AIService`, new `textual` optional dependency in `pyproject.toml`, new documentation `docs/console.md` and `docs/notebooklm.md`.
Additional changes: `agent/commands/check.py` — added `INCONCLUSIVE` detection with structured logging when all governance agents fail; `agent/sync/notebooklm.py` — improved error handling for expired authentication.
Workflows affected: None modified — all existing workflows are read-only inputs to the console. Existing `AIService` and provider infrastructure are reused as-is.
Risks identified: `textual` is a new dependency (~3MB). Streaming support needs a new method on `AIService` to yield chunks rather than accumulate. Token counting requires integration with existing `token_manager`.

## Test Strategy

- Unit tests: Conversation session CRUD (create, list, resume, delete) against SQLite. Token budget pruning logic. Workflow/role discovery from filesystem. Provider switching. Command parsing (`/help`, `/provider`, `/new`, etc.).
- Integration tests: Launch TUI in headless mode (`textual run --headless`), verify widget rendering and keyboard navigation. Verify streaming output against a mock AI provider.
- Manual verification: Launch `agent console` in a real terminal, verify split-pane layout, Tab navigation, `/help`, `/new`, `/conversations`, `/delete`, `/quit`, `/provider`, streaming responses, and conversation persistence across restarts.

## Rollback Plan

Remove the `console` command from `cli.py` and delete the `agent/tui/` package. The `textual` dependency lives in an optional group (`console`) so removal has zero impact on existing commands.

## Copyright

Copyright 2026 Justin Cook
