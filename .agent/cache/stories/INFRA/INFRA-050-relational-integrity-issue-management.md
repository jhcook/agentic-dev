# INFRA-050: Relational Integrity & Issue Management

## State

DRAFT

## Problem Statement

As the number of artifacts grows, ensuring Stories, Plans, and ADRs are correctly linked is difficult. Broken links and orphan stories reduce visibility.

## User Story

As a Project Manager, I want the agent to automatically maintain links between artifacts so that the "Relational Graph" of the project is always accurate.

## Acceptance Criteria

- [ ] **Orphan Detection**: A workflow scans for Stories not linked to any Plan or ADR.
- [ ] **Automated Linking**: If a Story description mentions "ADR-001", the agent automatically updates the `Linked ADRs` relation property.
- [ ] **Notification System**: The agent adds comments to Notion pages if it detects missing required fields that it cannot fix automatically.

## Non-Functional Requirements

- **Performance**: Scanning shouldn't take minutes. Use filtered queries.

## Linked ADRs

- ADR-010: Model Context Protocol

## Impact Analysis Summary

- **Components Touched**:
  - `.agent/workflows/notion_janitor.md`: logic for linking and comments.
- **Risks**:
  - False positives in text matching (e.g. "not an adr-001").

## Test Strategy

- **Manual Verification**:
  - Create a story mentioning "ADR-010" in the text but not the property.
  - Run janitor.
  - Verify property is updated.
  - Create an orphan story. Run janitor. Verify comment is added.

## Rollback Plan

- Disable the janitor workflow.
