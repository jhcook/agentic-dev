# INFRA-039: Enhance Voice Agent Tool Capabilities

## State

COMMITTED

## Problem Statement

The voice agent currently has access to tools but lacks a deep understanding of code structure or operational context. It cannot effectively explain how tools work or assist with complex operational tasks because it treats tools as "black boxes". This limits its utility as a pair programmer.

## User Story

As a Developer, I want the Voice Agent to be deeply conversant with the agent's tools and underlying source code, so that it can answer technical questions, explain how things work, and assist with operational activities (like debugging or deploying) without me needing to leave the voice interface.

## Acceptance Criteria

- [ ] **Enhanced System Prompt**: The `VoiceOrchestrator` system prompt must explicitly detail tool usage strategies and encourage tool-first problem solving.
- [ ] **Meta Tool Enhancements**:
  - [ ] `create_tool` (was `draft_new_tool`): Allow creating tools anywhere within the repository (source control boundary).
  - [ ] **Hot Reloading**: valid tools created by `create_tool` must be loaded and available for use immediately without restarting the agent.
  - [ ] **Syntax Validation**: Use `ast.parse` to validate code before saving to prevent breaking the registry.
  - [ ] `read_tool_source`: Allow reading existing tool code to understand patterns.
  - [ ] **Silent Reading**: Logic to ensure the agent does not read code blocks out loud (UX).
  - [ ] `get_installed_packages`: Allow checking available libraries.
  - [ ] `list_capabilities`: Return rich metadata (docstrings) for all tools.
- [ ] **Tool Refactoring**:
  - [ ] `project.py`: Implement actual filtering for `list_stories` and improve docstrings.
  - [ ] `architect.py`: Ensure `list_adrs` finds all relevant decision records.
  - [ ] `security.py`: Update scan tool to accept file paths for broader usability.
  - [ ] `qa.py`: Robustness checks for test runners.
- [ ] **Observability**:
  - [ ] Log content of created tools.
  - [ ] Trace tool execution and creation.

## Non-Functional Requirements

- **Usability**: Tools must have clear, descriptive docstrings that the LLM can understand.
- **Safety**:
  - Tool creation confined to the repository root (cannot write outside repo).
  - Security override: User accepts RCE risks as this is a developer tool.
- **Performance**: Tool inspection should be fast enough for real-time voice interaction.

## Linked ADRs

- None

## Impact Analysis Summary

Components touched: `backend/voice/orchestrator.py`, `backend/voice/tools/*.py`
Workflows affected: Voice interaction
Risks identified: Agent might hallucinate tool capabilities if docstrings are too vague; Code injection risks in tool creation (mitigated by directory restrictions).

## Test Strategy

- Manual verification of tool usage via voice commands.
- Verify that `create_tool` correctly writes valid python files to the target directory.
- Verify that the agent can "explain" what a tool does by reading its source.

## Rollback Plan

- Revert changes to tool files and orchestrator prompt.
