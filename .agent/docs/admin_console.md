# Agent Management Console

The Agent Management Console is a visual dashboard for the Agentic Voice system. It consists of a React-based frontend and a Python FastAPI backend, managed as a single unit via the `agent` CLI.

## Quick Start

Launch the console with:

```bash
agent admin start
```

This will concurrently start:

1. **Backend API**: `http://127.0.0.1:8000`
2. **Frontend UI**: `http://127.0.0.1:8080`

> **Note**: Both services bind explicitly to `127.0.0.1` (localhost) for security. They are not accessible from the external network.

## Architecture

The console follows a split-stack architecture to allow independent scaling and modern frontend development while keeping close integration with the Python backend logic.

### Components

#### 1. Frontend (`.agent/web/`)

- **Tech Stack**: React 19, TypeScript, Vite, Tailwind CSS.
- **Role**: Provides the user interface for agent management, visualization, and interaction.
- **Communication**: Proxies all requests to `/api` -> `http://127.0.0.1:8000`.

#### 2. Backend (`.agent/src/backend/routers/admin.py`)

- **Tech Stack**: FastAPI, Python 3.14 (or latest).
- **Role**: Exposes management APIs (e.g., `/api/admin/health`, `/api/stories`).
- **Integration**: Imports directly from the `agent` core logic to perform actions.

#### 3. CLI Orchestrator (`agent admin`)

- **Role**: Process manager.
- **Behavior**:
  - **`start`**: Launches services in detached mode (background). Writes PIDs to `.agent/run/admin.json`.
  - **`start --follow`**: Streams logs to console (Ctrl+C stops streaming but keeps services running).
  - **`stop`**: Sends `SIGTERM` to running processes and cleans up PID file.
  - **`status`**: Checks if processes are running.

## Development

### Directory Structure

```text
repo/
├── .agent/
│   ├── src/
│   │   ├── agent/commands/admin.py   # CLI Orchestrator
│   │   └── backend/routers/admin.py  # Backend API
│   └── web/                          # Frontend Source (Vite project)
└── README.md
```

### Extending the Console

1. **Add API Endpoint**:
   - Create route in `.agent/src/backend/routers/`.
   - Register in `.agent/src/backend/main.py`.

2. **Add UI Component**:
   - Add React component in `.agent/web/src/`.
   - Call API via relative path `/api/...` (the Vite proxy handles routing).

## Troubleshooting

- **"ModuleNotFoundError: No module named 'fastapi'"**:
  - The agent environment is missing dependencies. Install them: `pip install fastapi uvicorn`.

- **"Error: '.agent/web' directory not found"**:
  - Ensure the `.agent/web` directory exists. If it's missing, you may need to re-run the implementation or restoration steps.

- **Port Conflicts**:
  - Ensure ports `8000` and `8080` are free.
