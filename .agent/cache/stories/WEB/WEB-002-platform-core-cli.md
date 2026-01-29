# WEB-002: Platform Core & CLI

## State

COMMITTED

## Problem Statement

The "Agent Console" proposed in WEB-001 needs a foundation. We need to initialize the frontend codebase and provide a unified CLI interface to manage its lifecycle (start/stop/build), so developers don't have to switch contexts between `agent` CLI and `npm`.

## User Story

As a Developer, I want to run `agent admin start` to launch the Management Console servers (Frontend + Backend), so I can instantly access the visual dashboard without manually running multiple terminal commands.

## Acceptance Criteria

- [ ] **CLI**: Implement `agent admin start` command:
  - Use `asyncio.create_subprocess_exec` to manage Uvicorn and Vite processes concurrently.
  - Propagate `SIGINT` (Ctrl+C) to terminate both child processes cleanly (avoid zombies).
  - Check port availability (8000/5173) before starting.
- [x] **Logging**: Implement standardized logging verbosity:
  - `-v`: INFO (High-level agent logs).
  - `-vv`: DEBUG (Detailed agent logs, libraries silenced).
  - `-vvv`: TRACE (Full logs including third-party libraries).
- [x] **Preflight**: Verify `agent pr` and preflight checks correctly display blocking reasons to the console on failure.
- [ ] **Frontend Init**: Initialize `web/` directory with `vite` (React + TypeScript + TailwindCSS).
  - Configure `vite.config.ts` to proxy `/api` -> `http://127.0.0.1:8000` (avoids CORS complexity).
- [ ] **Shell UI**: Create a basic Layout with Sidebar navigation (Voice, Config, Logs).
- [ ] **Admin API**: Create `backend/routers/admin.py` with a simple health check endpoint `/api/health`.

## Non-Functional Requirements

- **Security**: Admin services (Uvicorn & Vite) MUST bind explicitly to `127.0.0.1`. Do NOT bind to `0.0.0.0`.
- **Developer Experience**: `agent admin start` should support hot-reloading for both frontend and backend.

## Linked ADRs

- ADR-009

## Impact Analysis Summary

Components touched: `agent/commands/`, `web/`, `backend/routers/`.
Workflows affected: "Starting the Agent" becomes a single command.
Risks: Port conflicts, zombie processes if signal handling is poor.

## Test Strategy

- Manual: Run `agent admin start`, verify browser opens, backend responds, and hitting Ctrl+C stops everything.
- Automated: Test CLI process manager logic (mocking subprocess).

## Rollback Plan

- Delete `web/` folder.
- Remove `agent admin` command group.
