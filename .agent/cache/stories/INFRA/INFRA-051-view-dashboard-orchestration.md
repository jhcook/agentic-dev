# INFRA-051: Local Admin Dashboard

## State

COMMITTED

## Problem Statement

Stakeholders and Developers need a consolidated view of the project's status (Stories, Plans, ADRs) "at a glance".
The original plan to use Notion Views was blocked by API limitations.
The user needs a local "Admin Console" dashboard to visualize work while working with Git.

## User Story

As a Developer, I want to view a "Project Dashboard" in my local `agent admin` console (web UI), so that I can see active stories, backlog, and system health without context switching to a browser-based Notion instance that requires manual sync.

## Acceptance Criteria

- [ ] **Console Navigation**: Update existing `App.tsx` (or Layout) to add "Dashboard" and "Kanban" to the navigation.
- [ ] **Dashboard Tab**:
  - Stats Widgets (Active Stories, Pending PRs, Total ADRs).
  - Active Work List (Table of IN_PROGRESS items).
- [ ] **Kanban Tab**:
  - Columns: DRAFT, IN_PROGRESS, REVIEW, COMMITTED.
  - Read-only cards sorted by ID.
- [ ] **Backend API**: Add endpoints to `backend/main.py` (or new router) to serve:
  - `GET /api/stories`
  - `GET /api/stats`
- [ ] **Data Source**: Backend reads local `.agent/cache/all_stories.json` (or parses Markdown).

## Non-Functional Requirements

- **Consistency**: Match existing UI styles (Tailwind).
- **Security**: Strict Localhost binding (No `0.0.0.0`).
- **Speed**: Dashboard must load instantly.

## Linked ADRs

- ADR-019 (Global ID Strategy)
- WEB-002 (Platform Core)

## Impact Analysis Summary

- **Components Touched**:
  - `.agent/src/web/App.tsx`: Navigation updates.
  - `.agent/src/web/components/`: New Dashboard/Kanban components.
  - `.agent/src/backend/`: API updates.
- **Risks**:
  - None (Standard feature addition).

## Test Strategy

- **Manual**:
  - Run `agent admin start`.
  - Go to `localhost:8080` (or configured port).
  - Verify Dashboard loads and shows correct counts matching local files.

## Rollback Plan

- Revert changes to `App.tsx` and `backend/main.py` if issues arise.
- `git restore .agent/src/web/App.tsx .agent/src/backend/main.py`
