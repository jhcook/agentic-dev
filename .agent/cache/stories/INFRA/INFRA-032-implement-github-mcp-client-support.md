# INFRA-032: Implement GitHub MCP Client Support

## State

COMMITTED

## Problem Statement

The agent currently lacks a robust, programmable way to interact with GitHub repositories, issues, and pull requests. While the `gh` CLI exists, it is not designed for agentic tool use (parsing text output is brittle). GitHub Copilot's "Agent Mode" offers these capabilities but requires an expensive Copilot Pro+ subscription ($39/mo/user), which is cost-prohibitive for many users. We need a cost-effective solution that leverages the user's existing GitHub access.

## User Story

As a Developer, I want the agent to be able to connect to the GitHub MCP Server using my Personal Access Token, so that it can read repositories and manage issues/PRs directly and cost-effectively without needing a Pro+ subscription.

## Acceptance Criteria

- [ ] **Dependency**: `modelcontextprotocol` package is added to `pyproject.toml`.
- [ ] **Secret Management**: `agent secret` is updated to support `github` service (`agent secret set github token`).
- [ ] **Core Client**: `agent.core.mcp` package is created with an `MCPClient` capable of connecting to stdio servers.
- [ ] **CLI Commands**:
  - `agent mcp start <server>`: Interactive session with an MCP server works.
  - `agent mcp run <server> <tool>`: One-off tool execution works.
- [ ] **Onboarding**: `agent onboard` prompts for GitHub tool preference (`mcp` vs `gh`) and configures secrets/auth accordingly.
- [ ] **Configuration**: `github` server configuration is added to `agent/config.py` (defaulting to `npx -y @modelcontextprotocol/server-github`).
- [ ] **Cost Savings**: The solution relies solely on the GitHub API (PAT) and does not require Copilot subscriptions.

## Non-Functional Requirements

- **Security**: GitHub tokens must be stored securely using `agent secret`, never plain text env vars in logs.
- **Reliability**: The client must handle stdio connection drops gracefully.
- **Portability**: Must assume `npx` is available for running the default server.

## Linked ADRs

- ADR-010-model-context-protocol-adoption.md

## Impact Analysis Summary

Components touched: `agent/commands`, `agent/core`, `pyproject.toml`
Workflows affected: None (New capability)
Risks identified: Dependency on `npx` availability for the default server configuration.

## Test Strategy

- Unit tests for `MCPClient` protocol handling (mocking stdin/out).
- Manual verification using `agent mcp run github list_repositories` to verify E2E connectivity.

## Rollback Plan

- Revert changes to `pyproject.toml` and delete new files.
