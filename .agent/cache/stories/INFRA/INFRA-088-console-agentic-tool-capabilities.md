# INFRA-088: Console Agentic Tool Capabilities

## State

COMMITTED

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

## Non-Functional Requirements

- **Performance**: Tool calls and command execution should be responsive and provide feedback to the user with minimal latency.
- **Security**: Command execution must be sandboxed to the repository context, preventing unauthorized system access.
- **Compliance**: Adhere to all relevant security and compliance standards.
- **Observability**: Implement logging and monitoring to track tool usage and identify potential issues.

## Linked ADRs

- ADR-028 (Typer Synchronous CLI Architecture)
- ADR-002 (Security Controls)
- EXC-003 (Shell Execution for Agentic Tools)

## Linked Journeys

- JRN-088 (Console Agentic Tool Workflows)
- INFRA-087 (Terminal Console TUI — dependency)

## Impact Analysis Summary

Components touched:
- Agentic loop
- Tool/Function calling registry
- File system interaction components
- Shell command execution
- Chat panel display
- Provider management
- Session Persistence

Workflows affected:
- Code modification and testing
- Code exploration
- Automated code generation tasks

Risks identified:
- Security vulnerabilities due to unrestricted command execution.
- Performance degradation due to inefficient tool implementations.
- Incompatibilities with certain AI providers.

## Test Strategy

- Unit tests for individual tool implementations (`test_interactive_tools.py`).
- Integration tests for the agentic loop and tool registry (`test_streaming_agentic.py`, `test_agentic_loop.py`).
- End-to-end tests for complex workflows involving multiple tool calls.
- **Regression tests for stream routing** (`test_stream_routing.py`) — 10 tests verifying simple vs agentic path selection, `use_tools` flag propagation, retry preservation, command history, and /search registration.
- **Session Synchronization Tests** (`test_session.py`, `test_commands.py`) — verifying that `/provider` and `/model` update the persistent session.
- Security audits to identify potential vulnerabilities.
- Performance tests to measure tool call latency and command execution time.

## Rollback Plan

- Disable the agentic tool capabilities via a feature flag.
- Revert to the previous version of the codebase.

## Copyright

Copyright 2026 Justin Cook
