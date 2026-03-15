# INFRA-141: Migration Filesystem and Shell Modules

## State

COMMITTED

## Problem Statement

The filesystem and shell tools currently live in `agent/core/adk/tools.py` as part of `make_interactive_tools()`. This story migrates them into dedicated domain modules (`filesystem.py`, `shell.py`) in the new `agent/tools/` package, and adds new file operations (`move_file`, `copy_file`, `file_diff`).

Parent: INFRA-098

## User Story

As a **Platform Developer**, I want **filesystem and shell tools in dedicated domain modules** so that **they are organised by capability, independently testable, and enriched with new file operations.**

## Acceptance Criteria

- [ ] **AC-1**: `agent/tools/filesystem.py` implements: `read_file`, `edit_file`, `patch_file`, `create_file`, `delete_file`, `find_files`, `move_file`, `copy_file`, `file_diff`.
- [ ] **AC-2**: `agent/tools/shell.py` implements: `run_command`, `send_command_input`, `check_command_status`, `interactive_shell`.
- [ ] **AC-3**: All tools include path validation and sandbox enforcement (carried over from `make_interactive_tools()`).
- [ ] **AC-4**: Tools are registered as plain callables via `ToolRegistry.register()`.
- [ ] **Negative Test**: `move_file` and `copy_file` reject paths outside the sandbox.

## Non-Functional Requirements

- Security: Path validation and PII scrubbing preserved from original implementation.

## Linked ADRs

- ADR to be created: Centralised ToolRegistry Interface

## Linked Journeys

- JRN-072: Terminal Console TUI Chat

## Impact Analysis Summary

Components touched: `.agent/src/agent/tools/filesystem.py` (NEW), `.agent/src/agent/tools/shell.py` (NEW)
Workflows affected: File manipulation and command execution.
Risks identified: Must preserve existing sandbox enforcement behavior from `make_interactive_tools()`.

## Test Strategy

- Unit tests for each new tool function.
- Regression tests verifying identical behavior to original `make_interactive_tools()` implementations.
- Security tests for path traversal rejection on new `move_file`/`copy_file`.

## Rollback Plan

Revert to `agent/core/adk/tools.py` — original implementation is unchanged until INFRA-146.

## Copyright

Copyright 2026 Justin Cook
