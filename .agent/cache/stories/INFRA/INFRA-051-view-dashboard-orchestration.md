# INFRA-051: View & Dashboard Orchestration

## State

DRAFT

## Problem Statement

Different stakeholders need different views (Kanban for status, List for backlog, Gallery for stakeholders). Manual setup is tedious and inconsistent.

## User Story

As a Stakeholder, I want curated Dashboards automatically created by the agent so that I have high-level visibility without configuring Notion.

## Acceptance Criteria

- [ ] **Filtered Views**: The agent uses `update_database` to create/maintain specific views (e.g., "Developer Backlog" filtered by State=Draft/Ready).
- [ ] **Project Overview**: A top-level Page designated as "Dashboard" is updated with Rollup data (e.g., number of open stories).

## Non-Functional Requirements

- **Aesthetics**: Views should be clean and use consistent sorting/filtering.

## Linked ADRs

- ADR-010: Model Context Protocol

## Impact Analysis Summary

- **Components Touched**:
  - `notion_schema.json`: Define "Views" in the desired state.
  - `notion_setup.md`: Apply logic for Views.
- **Risks**:
  - Notion API support for creating Views is limited/complex. May need fallback to just creating the Database and asking user to add views if API doesn't support it fully (verify capabilities).

## Test Strategy

- **Manual Verification**:
  - Run setup.
  - Check Notion for "Developer Backlog" tab in the Database.

## Rollback Plan

- Delete views manually.
