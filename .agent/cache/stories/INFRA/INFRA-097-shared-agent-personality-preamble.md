# INFRA-097: Shared Agent Personality Preamble

## State

COMMITTED

## Problem Statement

`agent console` has a ~170-line **hardcoded** system prompt in `tui/app.py:_build_system_prompt()` (lines 72–173) that produces a competent but **clinical** agent persona. Its tone — "Assertive & Neutral", "No Apologies", "Minimalist" — is deliberately cold and mechanical.

By contrast, **Antigravity** (the external AI coding assistant) reads `GEMINI.md` and receives platform-level personality instructions that make it a **collaborative pair-programmer** — warm, explains its reasoning, acknowledges mistakes, and takes bounded initiative.

The console agent and Antigravity operate on the same codebase but feel like completely different assistants. Users expect a consistent experience.

The root cause is that `_build_system_prompt()` never reads `GEMINI.md` or any external personality file — the entire persona is inline Python strings.

## User Story

As a developer, I want `agent console` to have the same collaborative pair-programmer personality as Antigravity, so that my experience is consistent regardless of which interface I use.

## Design

Add `console` configuration to `.agent/etc/agent.yaml` with two keys:

```yaml
console:
  personality_file: GEMINI.md  # repo context: roles, workflows, philosophy
  system_prompt: |             # personality & communication style
    You are a collaborative pair-programmer embedded in this repository.
    You work alongside the developer — proactive but never surprising.

    ## Communication Style
    - Explain your reasoning when making decisions
    - Acknowledge mistakes warmly and correct course
    - Take proactive but bounded initiative
    - Ask for clarification rather than assuming
    - Format responses in markdown for readability
    - Be concise but not cold — you're a colleague, not a terminal
```

**How they compose**: `_build_system_prompt()` layers three things:
1. **`console.system_prompt`** — the personality preamble (from agent.yaml)
2. **`console.personality_file`** content — repo context (from GEMINI.md)
3. **Runtime context** — repo root, license header, project layout, tool instructions (generated at startup, as today)

If either config key is absent, that layer is skipped. If both are absent, the current hardcoded prompt is used as fallback.

This separation enables future provider integrations — each provider could have its own personality file or system prompt without touching GEMINI.md.

## Acceptance Criteria

- [ ] **AC-1: Config keys**. `agent.yaml` supports `console.system_prompt` (inline personality text) and `console.personality_file` (path to repo context file, relative to repo root).
- [ ] **AC-2: Console reads both**. `_build_system_prompt()` in `tui/app.py` reads both config values and composes them with runtime context into the final system prompt.
- [ ] **AC-3: Collaborative tone**. With the personality prompt configured, the console agent's responses reflect collaborative pair-programmer traits: explains reasoning, acknowledges mistakes warmly, takes proactive but bounded initiative, asks for clarification rather than assuming.
- [ ] **AC-4: Governance awareness**. With `GEMINI.md` configured as personality_file, the agent retains awareness of project roles (@Architect, @Security, @QA, etc.), workflows, and the Agentic Workflow philosophy.
- [ ] **AC-5: Graceful fallback**. If either/both config keys are missing, or the personality_file doesn't exist, the system falls back to the current hardcoded prompt without crashing.
- [ ] **AC-6: No commit changes**. `agent commit` is explicitly out of scope — its system prompt remains unchanged.
- [ ] **AC-7: Runtime context preserved**. The personality layers supplement (not replace) runtime-specific context that `_build_system_prompt()` currently generates: repo root, license header template, project layout, tool-specific instructions.

## Non-Functional Requirements

- **Performance**: File read adds < 50ms to console startup (single read, then cached via `_CACHED_SYSTEM_PROMPT`).
- **Security**: Personality file treated as plain text context only; no script execution.
- **Token budget**: Combined prompt (personality + runtime context) should remain within reasonable bounds — the current prompt is ~2500 tokens; personality file should not more than double this.
- **Observability**: Debug log emitted on personality load: `logger.debug("system_prompt.personality_loaded", extra={"path": ..., "chars": ...})`.

## Linked ADRs

_None required — this is a configuration change, not an architectural shift._

## Linked Journeys

_TBD_

## Impact Analysis Summary

- **Files modified**:
  - `.agent/etc/agent.yaml` — add `console.personality_file` key
  - `tui/app.py` — refactor `_build_system_prompt()` to read configured personality file
  - `core/config.py` — expose `console.personality_file` config (if not already dynamic)
- **Workflows affected**: Console chat, workflow invocations (`/commit`, `/preflight`, etc.), role invocations (`@security`, etc.)
- **Out of scope**: `agent commit` command in `commands/workflow.py`
- **Risks**:
  - Token budget increase if the personality file is too verbose
  - Personality drift if GEMINI.md is updated for external agents without considering console impact

## Test Strategy

1. **Unit**: `test_build_system_prompt_with_both_keys()` — set `console.system_prompt` and `console.personality_file`, verify both are included in the composed prompt.
2. **Unit**: `test_build_system_prompt_personality_file_only()` — only `personality_file` set, verify repo context is loaded, personality falls back.
3. **Unit**: `test_build_system_prompt_system_prompt_only()` — only `system_prompt` set, verify personality is used without repo context file.
4. **Unit**: `test_build_system_prompt_fallback_no_config()` — neither key set, verify current hardcoded prompt used.
5. **Unit**: `test_build_system_prompt_missing_file()` — `personality_file` points to nonexistent file, verify graceful fallback.
6. **Unit**: `test_build_system_prompt_includes_runtime_context()` — verify repo root, license header, project layout still present alongside personality layers.
7. **Manual QA**: Open `agent console`, send a chat message, verify the response has a collaborative (not clinical) tone.

## Rollback Plan

1. Revert `tui/app.py` to restore the fully inline hardcoded prompt.
2. Remove the `console` key from `agent.yaml`.
3. `GEMINI.md` is untouched throughout.

## Copyright

Copyright 2026 Justin Cook
