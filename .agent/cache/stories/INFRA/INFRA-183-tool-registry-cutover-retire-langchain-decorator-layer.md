# INFRA-183: Tool Registry Cutover — Retire LangChain Decorator Layer

## State

DRAFT

## Problem Statement

INFRA-145 established `ToolRegistry` in `agent/core/adk/tools.py` as a unified interface seam,
using a **coexistence strategy** — both interfaces now have a path to `ToolRegistry`, but the voice
agent still dispatches through 42 LangChain `@tool` decorators across 15 `backend/voice/tools/`
modules. This is the debt retirement story: complete the cutover so the voice agent routes all tool
calls through `ToolRegistry`, and eliminate LangChain as a hard dependency for tool dispatch.

**`tools.py` is NOT deleted** — it remains the canonical implementation. The
`backend/voice/tools/` `@tool` decorator layer is stripped, and the voice orchestrator is wired
to `ToolRegistry` as the sole tool source.

Parent: INFRA-098

## User Story

As a **Platform Developer**, I want **the voice agent's tool dispatch fully migrated off LangChain
`@tool` decorators and onto `ToolRegistry`** so that **there is a single source of truth for tool
access across both interfaces, and LangChain is no longer a required dependency for tool dispatch.**

## Acceptance Criteria

- [ ] **AC-1**: All 42 `@tool` decorators removed from `backend/voice/tools/*.py` — functions become
      plain callables.
- [ ] **AC-2**: All 15 `from langchain_core.tools import tool` imports removed from
      `backend/voice/tools/` (files: `git.py`, `security.py`, `docs.py`, `observability.py`,
      `list_capabilities.py`, `architect.py`, `interactive_shell.py`, `fix_story.py`,
      `workflows.py`, `custom/add_license.py`, `qa.py`, `project.py`, `get_installed_packages.py`,
      `create_tool.py`, `read_tool_source.py`).
- [ ] **AC-3**: `RunnableConfig` injection pattern replaced in `git.py`, `interactive_shell.py`,
      `fix_story.py`, `workflows.py`, `qa.py` — context injected via `ToolRegistry.__init__(repo_root=...)`
      so the function signatures no longer carry LangChain-specific parameters.
- [ ] **AC-4**: `backend/voice/tools/registry.py` updated to delegate to
      `ToolRegistry(repo_root=...).list_tools(all=True)` — re-exports the same callable set so
      the orchestrator needs only a one-line swap without touching import sites.
- [ ] **AC-5**: `backend/voice/orchestrator.py` binds tools via `ToolRegistry` — imports no longer
      reference `backend/voice/tools/registry.py` directly for the tool list.
- [ ] **AC-6**: `agent/core/feature_flags.py` `USE_UNIFIED_REGISTRY` flag removed (migration is
      complete; the flag was the pre-merge escape hatch).
- [ ] **AC-7**: OpenTelemetry span emitted per tool call (`tool.name`, `tool.duration_ms`,
      `tool.success`, `session_id`) via the existing `tool_security.py` tracing scaffold.
- [ ] **Negative Test**: `grep -r "from langchain_core.tools import tool" .agent/src/backend/`
      returns zero results.
- [ ] **Negative Test**: Full test suite passes — `agent preflight --base main` exits 0.

## Non-Functional Requirements

- **No functional regression**: voice agent tool surface is identical before and after — same
  function names, same signatures (minus `RunnableConfig`), same behaviour.
- **LangChain stays** as a dependency of the LLM/graph layer (`langgraph`,
  `langchain-google-genai`) — only `langchain_core.tools.tool` in the dispatch layer is removed.
- **LOC gate**: No single file introduced or modified exceeds 1000 LOC.
- **Compliance**: Tool execution events carry `tool.name` and `session_id` in the audit log
  (ADR-046).

## Linked ADRs

- ADR-043: Tool Registry Foundation
- ADR-046: OpenTelemetry Instrumentation

## Linked Journeys

- JRN-072: Terminal Console TUI Chat
- JRN-023: Voice Logic Orchestration
- JRN-031: Voice Agent Tool Integration

## Impact Analysis Summary

- **`backend/voice/tools/*.py`** (15 files): Remove `@tool` + `from langchain_core.tools import tool`.
  Mechanical change per file. The functions already work as plain callables — the decorator only
  added LangChain schema metadata.
- **`backend/voice/tools/registry.py`**: Swap to `ToolRegistry` delegation. Single import swap.
- **`backend/voice/orchestrator.py`**: 1–2 line swap in tool binding site.
- **`agent/core/feature_flags.py`**: Delete `USE_UNIFIED_REGISTRY` (7 lines).
- **`agent/core/adk/tool_security.py`**: Wire OTel span per-call (existing scaffold is in place).
- **Risk**: `RunnableConfig` removal in 5 files — confirm every caller supplies context via
  `ToolRegistry(repo_root=...)` before cutting. Add integration test covering repo_root injection.

## Test Strategy

- **Unit** (`test_orchestrator_adapter.py`): Verify orchestrator uses `ToolRegistry`, not direct
  `registry.py` imports. Mock `ToolRegistry.list_tools`.
- **Integration** (`test_tool_parity.py`): Assert tool name sets are identical between TUI and voice
  after migration (test already exists from INFRA-145).
- **Negative**: `grep -r "from langchain_core.tools import tool" .agent/src/backend/` = empty.
- **Regression**: `agent preflight --base main` full suite pass (1382+ tests).

## Rollback Plan

Git revert of the migration commit restores all `@tool` decorators. The `USE_UNIFIED_REGISTRY`
flag in `feature_flags.py` acts as the pre-merge escape hatch and is removed as part of AC-6 only
after all other ACs are verified green.

## Copyright

Copyright 2026 Justin Cook