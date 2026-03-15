# INFRA-143: Migration Project and Knowledge Modules

## State

COMMITTED

## Problem Statement

Project management tools (`match_story`) and knowledge access tools (`read_adr`, `read_journey`) are scattered across Console and Voice. This story consolidates them into dedicated `project.py` and `knowledge.py` modules with enriched capabilities including `read_story`, `read_runbook`, and `search_knowledge` (vector similarity).

Parent: INFRA-098

## User Story

As a **Platform Developer**, I want **project and knowledge tools in dedicated domain modules** so that **the agent can access stories, runbooks, ADRs, and journeys through a consistent interface with vector search.**

## Acceptance Criteria

- [ ] **AC-1**: `agent/tools/project.py` implements: `match_story`, `read_story`, `read_runbook`, `list_stories`, `list_workflows`, `fix_story`, `list_capabilities`.
- [ ] **AC-2**: `agent/tools/knowledge.py` implements: `read_adr`, `read_journey`, `search_knowledge` (vector similarity via existing ChromaDB index).
- [ ] **AC-3**: `search_knowledge` accepts a natural language query and returns ranked results from the vector index.
- [ ] **AC-4**: All tools registered via `ToolRegistry.register()`.
- [ ] **Negative Test**: `read_story` with a non-existent story ID returns a clear error.

## Non-Functional Requirements

- Performance: Vector search uses existing ChromaDB index — no new index creation.

## Linked ADRs

- ADR to be created: Centralised ToolRegistry Interface

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

## Copyright

Copyright 2026 Justin Cook
