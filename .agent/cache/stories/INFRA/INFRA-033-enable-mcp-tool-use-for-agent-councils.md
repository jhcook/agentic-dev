# INFRA-033: Enable MCP Tool Use for Agent Councils

## State

COMMITTED

## Problem Statement

The `env -u VIRTUAL_ENV uv run agent preflight`, `env -u VIRTUAL_ENV uv run agent impact`, `env -u VIRTUAL_ENV uv run agent panel`, and other council workflows currently rely purely on static git context (diffs). They are unable to dynamically query the environment, read referenced issues, or inspect files outside the immediate diff context. Although we now have an MCP Client (`env -u VIRTUAL_ENV uv run agent mcp`), it is disconnected from the `AIService` used by these councils.

## User Story

As a Developer, I want the Agent (Preflight Council, Governance Panel, etc.) to be able to autonomously use MCP tools (like `github:get_issue`, `filesystem:read_file`) so that it can provide deeper, context-aware analysis and verification (e.g., verifying a bug fix against the live GitHub issue).

## Acceptance Criteria

- [ ] **Tool Discovery**: `AIService` loads compatible MCP servers/tools from `agent.yaml`.
- [ ] **Prompt Injection**: Available tools are injected into the System Prompt (or native Function Calling API if supported by the provider) for the Agent.
- [ ] **Execution Loop**: The `AIService` (or a new `AgentLoop`) supports a "Reason -> Act -> Observe" loop:
    1. Agent requests a tool call.
    2. System executes tool via `MCPClient` (using existing auth/fallback).
    3. System feeds result back to Agent.
    4. Agent continues reasoning.
- [ ] **Tool Output Scrubbing**: All tool outputs (observations) MUST be passed through `SecureManager` scrubbing before being added to the conversation context.
- [ ] **Tool Allow-listing**: Implement configuration to restrict which tools are available to specific councils (e.g., `preflight` gets read-only tools, `implement` gets write tools).
- [ ] **CI Compatibility**: Ensure this works in CI using the `gh` token fallback (implemented in INFRA-032).
- [ ] **Configurable**: Users can enable/disable tool use for specific councils via config.

## Technical Notes

- Leverage the `mcp.client.stdio` client we built.
- Ensure `SecureManager` helps in avoiding leakage of sensitive tool outputs.
- **Architectural Constraint**: Keep the `AgentLoop` logic distinct from `AIService`.

## Impact Analysis Summary

- **Static Analysis**: 0 files impacted by reverse dependencies (New files are not yet integrated).
- **Components Touched**:
  - `agent.core.engine` (New: Executor, Parser, Typedefs) - Core ReAct logic.
  - `agent.core.security` (New: SecureManager) - Output scrubbing.
  - `agent.commands.workflow` (Fix) - Fixes `env -u VIRTUAL_ENV uv run agent pr` test skipping logic.
- **Workflows Affected**: `env -u VIRTUAL_ENV uv run agent pr` (Immediate fix), `env -u VIRTUAL_ENV uv run agent panel` (Future integration).
- **Risks**:
  - **Security**: Reliability of `SecureManager` is critical for tool output safety.
  - **Stability**: `AgentExecutor` introduces complex looping logic; potential for infinite loops if guards fail.
  - **Blast Radius**: Currently low (zero deps), will increase once `governance.py` imports `AgentExecutor`.
- **Breaking Changes**: None. Additive changes only.

## Non-Functional Requirements

- **Performance**: Agent loop execution overhead should not exceed 5 seconds per step.
- **Security**: All tool outputs must be scrubbed of PII/Secrets.
- **Reliability**: Graceful fallback if MCP server is unreachable.

## Rollback Plan

- Revert `agent/core/governance.py` and `agent/core/config.py` changes.
- Safe to revert as feature is opt-in via config.

## Test Strategy

- Integration tests simulating a "Council" session with mocked tools.
