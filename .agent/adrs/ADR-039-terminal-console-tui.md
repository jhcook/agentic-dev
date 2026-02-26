# ADR-039: Terminal Console TUI

## Status

ACCEPTED

## Context

Developers in SSH-only or terminal-only environments need an interactive, multi-turn conversation interface to the agent. The existing `agent query` command is single-shot and stateless — it cannot maintain conversation context, chain workflow actions, or cache tokens. GUI-based AI tools (Antigravity, Cursor) provide this experience, but terminal users are left without an equivalent.

## Decision

A new `agent console` command provides an interactive TUI built on the Textual framework. Key architectural decisions:

1. **Framework Choice (Textual)**: Textual was chosen over alternatives (curses, prompt_toolkit, urwid) because it provides a modern widget system, CSS-based layout, built-in headless testing (`app.run_test()`), and async-first architecture compatible with streaming AI responses.
2. **Streaming via `AIService.stream_complete()`**: A new `stream_complete()` generator method was added to `AIService` alongside the existing blocking `complete()`. Each provider (Gemini, Vertex, Anthropic, OpenAI, Ollama) implements its own streaming path. The method yields `str` chunks and handles provider-specific error recovery.
3. **Persistence Layer (SQLite `console.db`)**: Conversation sessions are stored in `{config.cache_dir}/console.db` using SQLite. The database is created with `0600` permissions (user-only read/write) per @Security requirements. Schema: `sessions(id, title, created_at)` and `messages(id, session_id, role, content, timestamp)`.
4. **Package Isolation (`agent/tui/`)**: The TUI is isolated in its own package to avoid polluting the core CLI. `textual` is declared as an optional dependency group (`console`) so it has zero impact on existing commands.
5. **Token Budget Pruning**: A `TokenBudget` class implements FIFO pruning of conversation history to stay within context window limits, preserving the system prompt and most recent turns.
6. **Disconnect Recovery Modal**: When a provider fails mid-stream, a modal dialog gives the user explicit choices (Retry, Switch Provider, Cancel) rather than silently failing or auto-switching.

## Consequences

- **Positive**: Terminal users get a conversational AI interface equivalent to GUI tools. Workflow chaining (`/implement` → `/preflight` → `/commit`) within a single session improves developer productivity.
- **Positive**: Headless testing via Textual's `app.run_test()` enables CI-compatible TUI tests without a real terminal.
- **Negative**: `textual` adds a new dependency (~3MB) but is isolated to the optional `console` group.
- **Negative**: `stream_complete()` adds a new code path to `AIService` that must be maintained alongside `complete()` for all providers.

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0.
