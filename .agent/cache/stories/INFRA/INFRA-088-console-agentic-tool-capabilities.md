# INFRA-088: Console Agentic Tool Capabilities

## State

DONE

## Problem Statement

Currently, the Terminal Console TUI (INFRA-087) lacks the ability to leverage agentic workflows for interacting with the codebase, limiting its utility for complex development tasks that require iterative tool usage and real-time feedback.

## User Story

As a developer using the Terminal Console, I want the console agent to be able to use tools for code interaction, file manipulation, and executing shell commands so that I can automate complex development workflows directly within the console.

## Acceptance Criteria

- [x] **Scenario 1**: Given a user prompt requiring file access, When the agent calls the `read_file` tool, Then the file content is read and provided to the agent for processing.
- [x] **Scenario 2**: Given a user prompt requiring code modification, When the agent calls the `edit_file` tool, Then the specified file is modified, and the changes are saved.
- [x] **Scenario 3**: Given a user prompt requiring execution of a command, When the agent calls the `run_command` tool, Then the command is executed, and the standard output and standard error streams to the chat panel in real-time.
- [x] **Scenario 4**: Given a user prompt requiring code search, When the agent calls the `find_files` or `grep_search` tool, Then the relevant files are identified and provided to the agent.
- [x] **Scenario 5**: When using a function-calling capable provider (Gemini, OpenAI, Anthropic), the agent can use the tool/function calling registry.
- [x] **Scenario 6**: When using a non-function-calling provider (GH CLI), the system gracefully degrades and informs the user of limited functionality.
- [x] **Condition**: The agentic loop must iteratively process tool calls until the AI completes its assigned task.
- [x] **Condition**: Commands must only be executed within the context of the repository, preventing arbitrary system access.
- [x] **Negative Test**: System handles invalid tool calls or errors within the executed commands gracefully, providing informative error messages to the user.
- [x] **Scenario 7**: When a tool call fails or returns an error, the TUI displays the error and prompts the user to retry the operation (similar to Antigravity's retry UX).
- [x] **Scenario 8**: Given the user runs `agent console --model <model-name>`, Then the console uses the specified model for AI completions instead of the provider default.
- [x] **Scenario 9**: When the AI streams a response (with or without tool calls), text appears in the chat panel incrementally as tokens arrive, not as a single block after completion.
- [x] **Scenario 10**: The sidebar displays a curated list of preferred models across all configured providers. Clicking a model switches the active provider and model for subsequent AI calls.
- [x] **Scenario 11**: Regular chat messages use simple text streaming, NOT the agentic ReAct loop. Only workflow and role invocations activate the agentic tool loop.
- [x] **Scenario 12**: `run_command` output streams to the chat panel line-by-line in real-time via the `on_output` callback, so users see progress during long-running commands.
- [x] **Scenario 13**: ↑/↓ arrow keys navigate command history in the input box, similar to a Unix shell.
- [x] **Scenario 14**: `/search <query>` searches the output panel. `n` and `r` keys navigate between matches.
- [x] **Scenario 15**: The `use_tools` flag is preserved during disconnect recovery retries, ensuring the correct streaming path is maintained.
- [x] **Scenario 16**: When the `/provider` or `/model` command is used, the active session is updated, and subsequently created sessions inherit these settings.
- [x] **Scenario 17**: ReAct "thoughts" displayed in the TUI are cleaned of raw JSON, `Action:`, and `Thought:` prefixes, providing a human-readable stream.
- [x] **Scenario 18**: ReAct parser handles Python-dict syntax (single-quoted keys/values) from LLM output via `ast.literal_eval` fallback, preventing tool execution failures.
- [x] **Scenario 19**: ReAct parser handles YAML-style tool inputs (frequently emitted by some models) via a robust fallback regex matching `tool:` and `tool_input:` blocks.
- [x] **Scenario 20**: The Agentic Execution Panel displays agent progress by clearly demarcating 'Step N' for each thought, tool call, and tool result.
- [x] **Scenario 21**: After invoking a `/workflow` or `@role`, follow-up messages continue the agentic ReAct loop with tools enabled, rather than falling back to simple streaming.
- [x] **Scenario 22**: Deep dive analysis completed — 8 dead/redundant code items, 4 optimizations, and 10 enhancement proposals identified and documented.

## Non-Functional Requirements

- **Performance**: Tool calls and command execution should be responsive and provide feedback to the user with minimal latency.
- **Security**: Command execution must be sandboxed to the repository context, preventing unauthorized system access.
- **Compliance**: Adhere to all relevant security and compliance standards.
- **Observability**: Implement logging and monitoring to track tool usage and identify potential issues.

## Linked ADRs

- ADR-028 (Typer Synchronous CLI Architecture)
- ADR-002 (Security Controls)
- ADR-040 (Agentic Tool-Calling Loop Architecture)
- EXC-003 (Shell Execution for Agentic Tools)
- EXC-004 (Python ast.literal_eval Fallback in ReAct Parser)

## Linked Journeys

- JRN-088 (Console Agentic Tool Workflows)
- INFRA-087 (Terminal Console TUI — dependency)

## Impact Analysis Summary

Components touched:
- Agentic loop
- Tool/Function calling registry (`read_file`, `patch_file`, `run_command`, etc.)
- File system interaction components
- Shell command execution
- Chat panel display
- Provider management
- Session Persistence
- User Documentation (`docs/console.md`)

Workflows affected:
- Code modification and testing
- Code exploration
- Automated code generation tasks
- **New Workflow**: Agentic continuation for multi-turn role and workflow tasks.

Risks identified:
- Security vulnerabilities due to unrestricted command execution.
- Performance degradation due to inefficient tool implementations.
- Incompatibilities with certain AI providers.

### User Impact

- **`patch_file` tool**: Provides a safer, more precise way to edit files compared to rewriting the entire file with `edit_file`.
- **Agentic Continuation**: Enables multi-turn conversations where the agent can continue to use tools, making complex, iterative tasks possible.

## Test Strategy

- Unit tests for individual tool implementations (`test_interactive_tools.py`).
- Integration tests for the agentic loop and tool registry (`test_streaming_agentic.py`, `test_agentic_loop.py`).
- End-to-end tests for complex workflows involving multiple tool calls.
- **Regression tests for stream routing** (`test_stream_routing.py`) — 10 tests verifying simple vs agentic path selection, `use_tools` flag propagation, retry preservation, command history, and /search registration.
- **Session Synchronization Tests** (`test_session.py`, `test_commands.py`) — verifying that `/provider` and `/model` update the persistent session.
- **ReAct parser tests** (`test_parser.py`) — verifying single-quoted dict parsing, `ast.literal_eval` fallback, and brace-counting with quoted strings.
- Security audits to identify potential vulnerabilities.
- Performance tests to measure tool call latency and command execution time.

## Deep Dive Findings (2026-03-01)

### Root Cause Analysis

- **Parser Bug**: `executor.py:_build_context()` uses `str(dict)` to format `tool_input` in ReAct history, producing single-quoted Python dicts. The LLM learns this format and reproduces it, causing `json.loads()` to fail. Fix: `ast.literal_eval` fallback in parser + `json.dumps()` in `_build_context`.
- **Agentic Continuation**: Follow-up messages after workflows/roles fell through to simple streaming. Fix: `_agentic_mode` state flag in `ConsoleApp`.

### Code Quality Items Identified

- Duplicate `search_codebase` / `grep_search` tools
- `TOOL_SCHEMAS` built at import time with `Path(".")`
- Dead `msg_count` query in `session.py`
- N+1 session list queries
- Token budget default (8192) too small for modern models
- `MCPClient.get_context()` is NotebookLM-specific in generic class

### Enhancement Candidates

- Native function calling (bypass ReAct text parsing for Gemini/OpenAI/Anthropic)
- Multi-turn agentic memory across messages
- Tool approval flow for destructive operations
- `/export` command, tab autocomplete, session tagging

## Rollback Plan

- Disable the agentic tool capabilities via a feature flag.
- Revert to the previous version of the codebase.

## Copyright

Copyright 2026 Justin Cook
