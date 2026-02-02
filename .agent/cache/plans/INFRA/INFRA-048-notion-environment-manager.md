# PLAN-notion-manager: Notion Environment Manager

## State

PROPOSED

## Related Story

- INFRA-048
- INFRA-049
- INFRA-050
- INFRA-051

## Summary

To fulfill the vision of agentic-dev as a self-healing, self-managing system for non-technical users, the agent needs to move beyond just syncing files. It must become the Architect of the Notion workspace itself—generating the environment, handling schema evolution, and fixing issues as they arise.

## Objectives

- **Infrastructure-as-Code (IaC) for Notion**: Store "Desired State" schema locally.
- **Idempotency**: Architecture must support re-running setup without side effects.
- **Self-Correction Loop**: Periodically check and fix Notion schema drift.
- **Dynamic UI Generation**: Automatically create Templates and Views.
- **Relational Integrity**: Maintain links between Stories, Plans, and ADRs.

## Milestones

- **M1: Schema Bootstrapping (INFRA-048)**
  - Agent can go from a blank Notion page to a fully functional ADR/Story environment with one command.
  - Self-healing properties.
- **M2: Notion Native Template Creation (INFRA-049)**
  - Users can click "New" in Notion and get a pre-formatted Story template.
  - Auto-ID assignment for manually created stories.
- **M3: Relational Integrity & Issue Management (INFRA-050)**
  - "Janitor" workflow to link artifacts.
  - Notification system for broken links.
- **M4: View & Dashboard Orchestration (INFRA-051)**
  - Curated views for Stakeholders vs Developers.
  - "Project Overview" rollup page.

## Risks & Mitigations

- **Risk**: Notion API Rate Limits.
  - **Mitigation**: Implement exponential backoff in the MCP client or workflows.
- **Risk**: User modifications breaking schema.
  - **Mitigation**: "Janitor" workflows and drift detection (Self-Healing).
- **Risk**: Complexity of Block conversion.
  - **Mitigation**: Use `notion-mcp-server` capabilities and start with specific, supported blocks (headers, text, checklists).
- **Risk**: Security / Over-permissioning.
  - **Mitigation**: Adopt **Least Privilege**. Notion Integration is shared ONLY with the specific Parent Page, not the whole workspace.

## Verification

- **Manual**: Running the bootstrap workflow on a fresh page creates the correct DBs.
- **Unit**: Diff Engine tests mock Notion API to verify drift detection.
- **Drift Test**: Deleting columns results in auto-restoration.
- **User Test**: A non-technical user can create a Story in Notion and have it sync/link correctly.
