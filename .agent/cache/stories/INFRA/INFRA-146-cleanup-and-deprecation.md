# INFRA-146: Voice Tool Migration & LangChain Deprecation

## State

COMMITTED

## Problem Statement

INFRA-145 established `ToolRegistry` in `agent/core/adk/tools.py` as the unified tool access layer,
using a **coexistence** strategy — the registry wraps the existing tools without deleting legacy code.
INFRA-146 completes the migration by removing LangChain's `@tool` decorator dependency from the 15
`backend/voice/tools/` modules and ensuring the voice orchestrator routes all tool calls through
`ToolRegistry` rather than the legacy `registry.py` aggregator.

**`agent/core/adk/tools.py` is NOT deleted** — it is the canonical implementation. Only the
LangChain decorator layer inside `backend/voice/tools/` is removed.

Parent: INFRA-098

## User Story

As a **Platform Developer**, I want **the LangChain `@tool` decorator layer removed from all voice tools**
so that **the voice agent uses the same `ToolRegistry` as the console interface, eliminating the
dual-registry divergence and LangChain as a hard runtime dependency for tool dispatch.**

## Acceptance Criteria

- [ ] **AC-1**: All 42 `@tool` decorators removed from `backend/voice/tools/*.py` — functions become
      plain callables registered via `ToolRegistry`.
- [ ] **AC-2**: All 15 `from langchain_core.tools import tool` imports removed from
      `backend/voice/tools/` (15 files: `git.py`, `security.py`, `docs.py`, `observability.py`,
      `list_capabilities.py`, `architect.py`, `interactive_shell.py`, `fix_story.py`, `workflows.py`,
      `custom/add_license.py`, `qa.py`, `project.py`, `get_installed_packages.py`, `create_tool.py`,
      `read_tool_source.py`).
- [ ] **AC-3**: `RunnableConfig` injection pattern replaced in `git.py`, `interactive_shell.py`,
      `fix_story.py`, `workflows.py`, `qa.py` — context passed via `ToolRegistry` config param
      (the `config` arg already reserved in `ToolRegistry.list_tools()`).
- [ ] **AC-4**: `backend/voice/tools/registry.py` updated (not deleted) to re-export plain callables
      from `ToolRegistry` so the voice orchestrator needs only a one-line swap.
- [ ] **AC-5**: `backend/voice/orchestrator.py` binds tools via
      `ToolRegistry(repo_root=...).list_tools(all=True)` instead of importing from
      `backend/voice/tools/registry.py` directly.
- [ ] **AC-6**: `feature_flags.USE_UNIFIED_REGISTRY` flag removed (no longer needed — migration
      complete and fully committed).
- [ ] **AC-7**: OpenTelemetry span emitted per tool call (`tool.name`, `tool.duration_ms`,
      `tool.success`) via `tool_security.py`'s existing tracing scaffolding.
- [ ] **Negative Test**: `from langchain_core.tools import tool` grep across `backend/voice/tools/`
      returns zero results post-migration.
- [ ] **Negative Test**: Full test suite passes with `langchain-core` removed from
      `pyproject.toml` optional deps (or pinned to `extras = []`).

## Non-Functional Requirements

- No functional regression: voice agent tool surface must be identical before and after (same 42
  callable names, same signatures).
- LangChain remains a dependency of the voice LLM layer (`langgraph`, `langchain-google-genai`) —
  only the `@tool` decorator import in the dispatch layer is removed.
- Compliance: tool execution events must carry `tool.name` and requesting `session_id`
  in the audit log (ADR-046).

## Linked ADRs

- ADR-043: Tool Registry Foundation
- ADR-046: OpenTelemetry Instrumentation

## Linked Journeys

- JRN-072: Terminal Console TUI Chat
- JRN-023: Voice Logic Orchestration
- JRN-031: Voice Agent Tool Integration

## Impact Analysis Summary

- **`backend/voice/tools/*.py`** (15 files): Remove `@tool` + `from langchain_core.tools import tool`.
  Decorator removal is mechanical — each function becomes a plain `def`.
- **`backend/voice/tools/registry.py`**: Swap `from .X import @tool_fn` exports for
  `ToolRegistry(repo_root).list_tools(all=True)` delegation.
- **`backend/voice/orchestrator.py`**: One-line swap in tool binding.
- **`agent/core/feature_flags.py`**: Delete `USE_UNIFIED_REGISTRY` flag (migration is done).
- **`agent/core/adk/tools.py`**: No changes — this is the canonical implementation.
- Risk: `RunnableConfig` removal in 5 files requires care — some tools use it for repo_root
  injection; confirm `ToolRegistry.__init__(repo_root=...)` covers all cases.

## Test Strategy

- **Unit**: Mock `ToolRegistry.list_tools()` in `test_orchestrator_adapter.py` — verify orchestrator
  uses registry, not legacy imports.
- **Integration**: `test_tool_parity.py` (already exists from INFRA-145) verifies tool name sets
  are identical between TUI and voice after migration.
- **Negative**: `grep -r "from langchain_core.tools import tool" .agent/src/backend/` returns empty.
- **Regression**: `agent preflight --base main` full suite pass.

## Rollback Plan

Git revert of the migration commit restores all `@tool` decorators. No feature flag needed
post-INFRA-146 — the `USE_UNIFIED_REGISTRY` flag in `feature_flags.py` is the pre-merge escape
hatch and is deleted as part of **AC-6**.

## Copyright

Copyright 2026 Justin Cook
