# WEB-005: Governance Desk

## State

OPEN

## Problem Statement

Governance workflows (`story`, `plan`, `runbook`, `preflight`) are currently CLI-only, which makes it hard to visualize the state of work, track progress, or easily edit artifacts without context switching.

## User Story

As a User, I want a visual Governance Desk to manage Stories, Plans, and Runbooks, and run Preflight checks visually, so that I can manage the agent's development lifecycle more intuitively.

## Acceptance Criteria

- [ ] **Artifact Browser**: Tree/List view of all Stories, Plans, and Runbooks.
- [ ] **Artifact Editor**: Markdown editor with preview for editing artifacts.
- [ ] **Kanban Board**: Drag-and-drop interface to move Stories between states (OPEN, PLANNED, COMMITTED).
- [ ] **Visual Preflight**: UI to run `agent preflight` and view the results report interactively.

## Linked ADRs

- ADR-009 (Agent Console Architecture)
