# INFRA-146: Cleanup and Deprecation

## State

COMMITTED

## Problem Statement

After all tools have been migrated to `agent/tools/` and both interfaces consume the `ToolRegistry`, the legacy implementations must be removed. This story deletes the old tool files, strips all LangChain `@tool` decorators, and finalises audit logging.

Parent: INFRA-098

## User Story

As a **Platform Developer**, I want **legacy tool implementations and LangChain dependencies removed** so that **there is a single source of truth with no dead code.**

## Acceptance Criteria

- [ ] **AC-1**: `.agent/src/agent/core/adk/tools.py` is DELETED — all functions have been migrated.
- [ ] **AC-2**: `.agent/src/backend/voice/tools/` directory is DELETED — all tools migrated to `agent/tools/domain/` or consolidated.
- [ ] **AC-3**: All `from langchain_core.tools import tool` imports are removed from migrated code.
- [ ] **AC-4**: All `@tool` decorators are removed — tools are plain callables registered via `ToolRegistry`.
- [ ] **AC-5**: `RunnableConfig` injection patterns in `qa.py`, `workflows.py`, `git.py`, `fix_story.py`, `interactive_shell.py` are replaced with equivalent context passing via the registry.
- [ ] **AC-6**: Standardised OpenTelemetry tracing and structured audit logging implemented for all tool execution and permission elevation events.
- [ ] **Negative Test**: Importing from deleted modules raises `ImportError`.

## Non-Functional Requirements

- Compliance: Audit log events for tool creation, import, and restriction removal standardised.

## Linked ADRs

- ADR-043: Tool Registry Foundation

## Linked Journeys

- JRN-072: Terminal Console TUI Chat
- JRN-023: Voice Logic Orchestration
- JRN-031: Voice Agent Tool Integration

## Impact Analysis Summary

Components touched: `agent/core/adk/tools.py` (DELETE), `backend/voice/tools/` (DELETE — 15+ files), `backend/voice/tools/registry.py` (DELETE)
Workflows affected: All tool-related workflows — this is the final cutover.
Risks identified: Any code still importing from deleted modules will break — requires thorough grep verification.

## Test Strategy

- Verify no remaining imports from deleted modules via `grep -r "from agent.core.adk.tools" .agent/src/`.
- Verify no remaining `from langchain_core.tools import tool` in any migrated code.
- Full test suite pass after deletion.

## Rollback Plan

Feature flag `USE_UNIFIED_REGISTRY=false` can revert to legacy implementations if the deletion branch is not merged.

## Copyright

Copyright 2026 Justin Cook
