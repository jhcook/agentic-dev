# INFRA-143: Migration Project and Knowledge Modules

## State

COMMITTED

## Problem Statement

Project management tools (`match_story`) and knowledge access tools (`read_adr`, `read_journey`) are scattered across Console and Voice. This story consolidates them into dedicated `project.py` and `knowledge.py` modules with enriched capabilities including `read_story`, `read_runbook`, and `search_knowledge` (vector similarity).

Parent: INFRA-098

## User Story

As a **Platform Developer**, I want **project and knowledge tools in dedicated domain modules** so that **the agent can access stories, runbooks, ADRs, and journeys through a consistent interface with vector search.**

## Acceptance Criteria

- [x] **AC-1**: `agent/tools/project.py` implements: `match_story`, `read_story`, `read_runbook`, `list_stories`, `list_workflows`, `fix_story`, `list_capabilities`.
- [x] **AC-2**: `agent/tools/knowledge.py` implements: `read_adr`, `read_journey`, `search_knowledge` (vector similarity via existing ChromaDB index).
- [x] **AC-3**: `search_knowledge` accepts a natural language query and returns ranked results from the vector index.
- [ ] **AC-4**: All tools registered via `ToolRegistry.register()`.
- [x] **AC-5 (Negative Test)**: `read_story` with a non-existent story ID returns a clear error string.
- [x] **AC-6**: All tool functions use `validate_safe_path` from `tool_security` for path traversal prevention.
- [x] **AC-7**: `agent/tools/telemetry.py` provides `track_tool_usage` decorator with structured logging, OTel spans, and in-memory metrics.
- [x] **AC-8**: Unit tests for `knowledge`, `project`, `telemetry`, and `tool_security` modules pass (27/27 in `tests/agent/`).
- [x] **AC-9**: Colocated `tests/` directories removed from `.agent/src/agent/` (INFRA-171 cleanup).
## Non-Functional Requirements

- Performance: Vector search uses existing ChromaDB index — no new index creation.

## Linked ADRs

- ADR-043: Tool Registry Foundation

## Linked Journeys

- JRN-072: Terminal Console TUI Chat
- JRN-023: Voice Logic Orchestration

## Impact Analysis Summary

Components touched: `.agent/src/agent/tools/project.py` (NEW), `.agent/src/agent/tools/knowledge.py` (NEW)
Workflows affected: Story management and knowledge retrieval.
Risks identified: Vector search depends on ChromaDB being initialised.

## Test Strategy

- Unit tests for story/runbook reading with mock filesystem.
- Integration test: `search_knowledge` against test vector index.

## Rollback Plan

Revert to original scattered implementations — no deletion until INFRA-146.

## Session Changes (2026-03-27)

- **Fix**: `knowledge.py` and `project.py` imported non-existent `sanitize_path` from `path_security` — rewired to `validate_safe_path` from `tool_security`.
- **Fix**: `knowledge.py` top-level import of `rag_service` caused transitive `ModuleNotFoundError` (`rag.py` → `agent.config`). Made import lazy inside `search_knowledge()`.
- **Fix**: `search.py` had trailing runbook markdown junk (`~~~`, `[MODIFY] CHANGELOG.md`) causing `SyntaxError` — removed.
- **Fix**: `test_migration_verification.py` had 38 lines of runbook markdown embedded after valid Python — removed. Anchored paths to repo root via `__file__`, updated expected test directories to match actual hierarchy.
- **Fix**: `test_knowledge.py` had invalid multi-line `with` syntax and mocked a non-existent `config` object — rewrote to match actual API (`repo_root` param, async `search_knowledge`, `tmp_path` fixtures).
- **Fix**: `test_project.py` had same issues — rewrote to match actual API with `tmp_path` filesystem tests.
- **Fix**: `test_runbook_generation.py` was truncated (unclosed bracket `SyntaxError`) — completed the test function body.
- **Cleanup**: Removed 7 colocated `tests/` directories from `.agent/src/agent/` (INFRA-171 migration leftovers): `tools/tests`, `core/tests`, `core/auth/tests`, `core/ai/tests`, `core/implement/tests`, `commands/tests`, `sync/tests`.

## Copyright

Copyright 2026 Justin Cook
