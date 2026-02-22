# WEB-002-runbook.md

## Status

ACCEPTED

## Goal

Implement the foundational "Agent Console" infrastructure.

1. **Frontend**: Initialize React/Vite/Tailwind in `web/`.
2. **CLI**: `env -u VIRTUAL_ENV uv run agent admin start` to launch Frontend (5173) and Backend (8000) concurrently.
3. **API**: Basic Admin Router (`routers/admin.py`) for health checks.

## Panel Review Findings

### @Architect

**Sentiment**: Positive
**Advice**:

- **Process Management**: `env -u VIRTUAL_ENV uv run agent admin start` must use `asyncio.create_subprocess_exec` to manage child processes (Uvicorn/Vite) and catch `SIGINT` to prevent zombie processes.
- **Proxy**: Vite's `server.proxy` is the correct pattern to avoid CORS issues locally.

### @Security

**Sentiment**: Warning (Network Binding)
**Advice**:

- **Constraint**: Admin services MUST bind to `127.0.0.1`. Do not expose management interfaces on `0.0.0.0`.
- **Validation**: Ensure the proxy config points explicitly to localhost.

### @Web

**Sentiment**: Positive
**Advice**:

- **Stack**: Standardize on React+Vite+Tailwind for speed and ecosystem support.

## Implementation Steps

### 1. Initialize Frontend

**Location**: `web/`

- Run `npm create vite@latest web -- --template react-ts`.
- Install dependencies: `npm install -D tailwindcss postcss autoprefixer`, `npx tailwindcss init -p`.
- Configure `vite.config.ts`:

  ```typescript
  server: {
    host: "127.0.0.1",
    proxy: {
      "/api": "http://127.0.0.1:8000"
    }
  }
  ```

### 2. Implement Admin API

**File**: `src/backend/routers/admin.py`

- Create `APIRouter` with prefix `/api/admin`.
- Add endpoint `GET /health` returning `{"status": "ok", "version": "..."}`.
- Register router in `backend/main.py`.

### 3. Implement CLI Command

**File**: `src/agent/commands/admin.py`

- Create `AsyncProcessManager` class to handle:
  - `start_server()`: Launch Uvicorn (`127.0.0.1:8000`).
  - `start_client()`: Launch Vite (`npm run dev`).
  - `stop()`: Send SIGTERM to children.
- Use `asyncio.gather` to keep both running.
- Register `admin` command group in `agent/cli.py` (or via Typer auto-discovery).

## Verification Plan

### Automated Tests

1. **CLI Unit Test**: Mock `subprocess` to verify `env -u VIRTUAL_ENV uv run agent admin start` attempts to launch both commands and handles `KeyboardInterrupt`.
2. **API Test**: `TestClient` request to `/api/admin/health`.

### Manual Verification

1. Run `env -u VIRTUAL_ENV uv run agent admin start`.
2. Open `http://localhost:5173`.
3. Verify page loads (React logo).
4. Open `http://localhost:5173/api/admin/health` (Proxy test).
5. Hit `Ctrl+C` in terminal -> Verify both processes exit.
