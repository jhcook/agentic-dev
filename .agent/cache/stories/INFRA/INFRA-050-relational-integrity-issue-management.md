# INFRA-050: Relational Integrity & Issue Management

## State

In Progress## Problem Statement

As the number of artifacts grows, ensuring Stories, Plans, and ADRs are correctly linked is difficult. Broken links and orphan stories reduce visibility.

## User Story

As a Project Manager, I want the agent to automatically maintain links between artifacts so that the "Relational Graph" of the project is always accurate.

## Acceptance Criteria

- [ ] **Orphan Detection**: A workflow scans for Stories not linked to any Plan or ADR.
- [ ] **Automated Linking**: If a Story description mentions "ADR-001", the agent automatically updates the `Linked ADRs` relation property.
- [ ] **Notification System**: The agent adds comments to Notion pages if it detects missing required fields that it cannot fix automatically.
- [ ] **Efficiency**: Uses Notion API filtering to fetch only relevant pages (no full scans).
- [ ] **Idempotency**: Comments are only added if they don't already exist (No spam).
- [ ] **Robustness**: Invalid ID references (e.g. ADR-999) are logged as warnings but do not crash the process.

## Technical Approach

- **Modularity**: Implement `NotionJanitor` class in `agent.janitor` (or `agent.core.notion`).
- **Patterns**: Use `check_ssl_error` for all API calls.

## Non-Functional Requirements

- **Performance**: Scanning shouldn't take minutes. Use filtered queries.
- **Observability**: Log counts of Orphans, Links, and Errors to stdout.
- **Security**: Do not log raw Page outputs (descriptions) to prevent data leaks.

## Linked ADRs

- ADR-010: Model Context Protocol

## Impact Analysis Summary

- **Components Touched**:
  - `agent/sync/janitor.py`: New service module.
  - `agent/sync/cli.py`: Add subcommand.
  - `agent/core/notion/client.py`: Shared client logic (Refactor opportunity).
- **Risks**:
  - **Infinite Loops**: Updating a page triggers a scan (avoid by manual trigger first).
  - **False Positives**: Text scanning needs robust regex `([A-Z]+-\d+)`.

## Test Strategy

- **Manual Verification**:
  - Create a story mentioning "ADR-010" in the text but not the property.
  - Run janitor.
  - Verify property is updated.
  - Create an orphan story. Run janitor. Verify comment is added.
  - Run janitor again. Verify NO duplicate comment is added.

## Rollback Plan

- Revert changes to `agent/sync/cli.py`.
