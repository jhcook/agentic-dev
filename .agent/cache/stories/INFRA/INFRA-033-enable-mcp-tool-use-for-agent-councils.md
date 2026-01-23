# INFRA-033: Enable MCP Tool Use for Agent Councils

## State

OPEN

## Problem Statement

The `agent preflight`, `agent impact`, `agent panel`, and other council workflows currently rely purely on static git context (diffs). They are unable to dynamically query the environment, read referenced issues, or inspect files outside the immediate diff context. Although we now have an MCP Client (`agent mcp`), it is disconnected from the `AIService` used by these councils.

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
- [ ] **CI Compatibility**: Ensure this works in CI using the `gh` token fallback (implemented in INFRA-032).
- [ ] **Configurable**: Users can enable/disable tool use for specific councils via config.

## Technical Notes

- Leverage the `mcp.client.stdio` client we built.
- Ensure `SecureManager` helps in avoiding leakage of sensitive tool outputs.

## Impact Analysis Summary

- Components touched: `agent.agent.core.ai`, `agent.core.mcp`.
- Workflows affected: `preflight`, `impact`, `panel`.
- Risks: Infinite loops, token exhaustion.

## Test Strategy

- Integration tests simulating a "Council" session with mocked tools.
