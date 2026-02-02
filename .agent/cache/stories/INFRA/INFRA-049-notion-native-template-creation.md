# INFRA-049: Notion Native Template Creation

## State

DRAFT

## Problem Statement

Currently, users must manually copy headers/structure when creating a new Story in Notion, leading to inconsistency. The agent should provide native Notion templates for one-click creation.

## User Story

As a Product Owner, I want to click "New" in Notion and have a pre-formatted Story template so that I can easily create valid stories without remembering the schema.

## Acceptance Criteria

- [ ] **Template Page**: The agent uses `create_page` to define "Template Pages" inside the Stories database.
- [ ] **Pre-population**: Template includes headers like `## Problem Statement`, `## User Story` mapped to Notion Blocks.
- [ ] **Self-Healing IDs**: If a user creates a Story without an ID, the agent (via a "Janitor" workflow) automatically assigns the next available `STORY-XXX` ID and updates the title.

## Non-Functional Requirements

- **Usability**: The template should be the default for new items in the database.

## Linked ADRs

- ADR-010: Model Context Protocol

## Impact Analysis Summary

- **Components Touched**:
  - `.agent/workflows/notion_janitor.md`: New workflow for ID assignment.
  - `notion_setup.md`: Update to create templates.
- **Risks**:
  - Conflicts in ID assignment if multiple users create stories offline (unlikely for Notion specific).

## Test Strategy

- **Manual Verification**:
  - Click "New" in Notion -> Verify Template appears.
  - Create a story "My Feature" -> Run janitor -> Verify title becomes "STORY-XXX: My Feature".

## Rollback Plan

- Delete template pages manually from Notion.
