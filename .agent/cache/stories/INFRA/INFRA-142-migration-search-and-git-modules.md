# INFRA-142: Migration Search and Git Modules

## State

REVIEW_NEEDED

## Problem Statement

Search tools (`search_codebase`, `grep_search`, `list_directory`) currently live in `agent/core/adk/tools.py`, and git tools are split between Console and Voice. This story creates dedicated `search.py` and `git.py` modules with enriched capabilities including AST-aware symbol lookup and git history/blame.

Parent: INFRA-098

## User Story

As a **Platform Developer**, I want **search and git tools in dedicated domain modules with AST-aware symbol lookup and rich git history** so that **the agent can navigate code semantically and inspect version history.**

## Acceptance Criteria

- [ ] **AC-1**: `agent/tools/search.py` implements: `search_codebase`, `grep_search`, `list_directory`, `find_symbol` (AST-aware), `find_references`.
- [ ] **AC-2**: `find_symbol` uses Python `ast` module to locate function/class definitions by name, not just text search.
- [ ] **AC-3**: `agent/tools/git.py` implements: `show_diff`, `blame`, `file_history`, `stash`, `unstash`, and basic commit/branch operations.
- [ ] **AC-4**: All tools registered via `ToolRegistry.register()`.
- [ ] **Negative Test**: `find_symbol` on a non-Python file returns a clear unsupported error.

## Non-Functional Requirements

- Performance: `find_symbol` should parse files lazily to avoid scanning entire repo.

## Linked ADRs

- ADR-043: Tool Registry Foundation

## Linked Journeys

- JRN-072: Terminal Console TUI Chat

## Impact Analysis Summary

Components touched: `.agent/src/agent/tools/search.py` (NEW), `.agent/src/agent/tools/git.py` (NEW)
Workflows affected: Code navigation and version control.
Risks identified: AST-aware search only works for Python — need clear error for other languages.

## Test Strategy

- Unit tests for `find_symbol` with various Python constructs (functions, classes, methods).
- Unit tests for `blame` and `file_history` output parsing.
- Integration test: `find_symbol` → `find_references` round-trip.

## Rollback Plan

Revert to `agent/core/adk/tools.py` — original search tools remain until INFRA-146.

## Copyright

Copyright 2026 Justin Cook
