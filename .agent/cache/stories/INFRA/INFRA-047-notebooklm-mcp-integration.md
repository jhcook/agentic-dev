# INFRA-047: NotebookLM MCP Integration

## State

DRAFT

## Problem Statement

Current research workflows are fragmented; NotebookLM offers superior synthesis but lacks direct integration with the agent. The manual authentication requirement for the `notebooklm-mcp-server` further complicates automation, requiring a headless/secret-based approach for smooth agent usage.

## User Story

As a Developer, I want to integrate the NotebookLM MCP server into the Agent's toolchain using `agent secret` for authentication and `agent.yaml` for configuration, so that the agent can autonomously perform deep research and context retrieval without manual browser interaction.

## Acceptance Criteria

- [ ] **Config Logic**: `agent.core.config` merged `agent.yaml` MCP server definitions with defaults.
- [ ] **Secret Injection**: The MCP Client automatically injects `NOTEBOOKLM_COOKIES` from the secret manager into the server environment.
- [ ] **NotebookLM Server**: The `notebooklm-mcp-server` is configured in `agent.yaml` and callable by the agent.
- [ ] **Verification**: `agent mcp list-tools notebooklm` returns valid tools (e.g. `create_note`) when authenticated via secrets.

## Non-Functional Requirements

- Performance
- Security
- Compliance
- Observability

## Linked ADRs

- ADR-010 (MCP Adoption)
- ADR-017 (Command Registry)

## Impact Analysis Summary

Components touched: `agent.core.config`, `agent.core.mcp`, `agent.yaml`
Workflows affected: Research, Preflight (if enabled)
Risks identified: Cookie expiration requires manual secret rotation.

## Test Strategy

- **Unit**: Verify `config.get_mcp_servers()` correctly merges defaults and YAML, and handles missing config gracefully.
- **Manual**: Configure `agent secret set notebooklm.cookies`, run `agent mcp list-tools notebooklm`, and verify tool list.

## Rollback Plan

How do we revert safely?
