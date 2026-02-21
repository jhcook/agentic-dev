# INFRA-052: Notion Environment Manager - Schema Bootstrapping

## State

COMMITTED

## Problem Statement

To enable a self-managing Notion workspace for non-technical users, the agent needs to be able to "bootstrap" the environment from scratch and ensure relational integrity. Currently, the agent has no visibility or control over the Notion schema.

## User Story

As a Product Owner, I want the agent to automatically create and maintain the required Notion Databases ("Stories", "Plans", "ADRs") so that I can start managing the project in Notion without manual setup.

## Acceptance Criteria

- [ ] **MCP Configuration**: The agent is configured to use the `notion-mcp-server` (via generic `mcp` command) with necessary secrets.
- [ ] **Schema Definition**: A "Desired State" schema is defined in `.agent/etc/notion_schema.json` (defining "Stories", "Plans", "ADRs" databases and their properties).
- [ ] **Schema Validation**: An automated check validates `notion_schema.json` syntax before execution.
- [ ] **Onboarding Integration**: The `env -u VIRTUAL_ENV uv run agent onboard` command prompts to configure Notion and runs the bootstrapping logic if enabled.
- [ ] **Self-Healing (Property Restoration)**: If a required property (e.g., "Status" in Stories) is missing, the agent adds it (Diff Engine).
- [ ] **Integration Test**: A manual test where we delete a database or property and verify the agent restores it.

## Non-Functional Requirements

- **Security**:
  - API Keys stored in Secret Manager.
  - **Data Safety**: Logs must NOT print raw API responses (mask sensitive data).
- **Idempotency**: Running the bootstrap command multiple times must be safe (e.g., only add missing properties, do not recreate DB).
- **Resilience**: Script must fail gracefully if `node`/`npx` is missing.
- **Observability**: CLI output should be verbose and user-friendly ("Found DB...", "Verifying Schema...").

## Linked ADRs

- ADR-010: Model Context Protocol

## Impact Analysis Summary

- **Components Touched**:
  - `agent.yaml`: Server config.
  - `notion_schema.json`: New file.
  - `.agent/scripts/notion_schema_manager.py`: Core logic.
- **Risks**:
  - Notion API complexity for `create_database`.
  - Identifying databases reliably (likely need to store IDs in a local mapping file).

## Test Strategy

- **Manual Verification**:
  - Run the bootstrap workflow.
  - Check Notion for created databases.
  - Delete a property.
  - Run workflow again.
  - Verify property is restored.

## Rollback Plan

- Delete the created Notion databases manually.
- Remove `notion_schema.json`.
