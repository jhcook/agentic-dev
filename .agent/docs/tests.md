# Test Suite

The Agent CLI test suite lives under `.agent/tests/` and uses `pytest` with configuration defined in `.agent/pyproject.toml`. The suite contains **~712 tests** across **148 test files** organized into 12 directories.

## Running Tests

```bash
# Run the full suite (see Known Issues below)
uv run pytest .agent/tests

# Run a specific directory
uv run pytest .agent/tests/commands

# Run a specific file
uv run pytest .agent/tests/commands/test_sync.py

# Run with verbose output
uv run pytest .agent/tests/commands -v

# Stop on first failure
uv run pytest .agent/tests -x
```

### Workaround: Run All Directories Individually

Due to a known collection hang (see below), use this to run the full suite reliably:

```bash
for d in admin backend cli commands core db e2e integration journeys sync unit voice; do
  echo "=== $d ==="
  uv run pytest ".agent/tests/$d" -q
done
```

## Test Directories

| Directory | Tests | Files | Description |
|-----------|------:|------:|-------------|
| `commands/` | 202 | 28 | CLI command unit tests — covers every `agent` subcommand (`sync`, `story`, `runbook`, `plan`, `pr`, `implement`, `preflight`, `mcp`, etc.) |
| `core/` | 156 | 23 | Core library tests — AI services, governance parsing, context loading, utilities, secret management, MCP client |
| `journeys/` | 135 | 53 | User journey validation — auto-generated tests asserting journey YAML structure, linked stories, and implementation file existence |
| `integration/` | 44 | 9 | Integration tests — NotebookLM sync, MCP authentication, Notion sync, end-to-end command flows |
| `voice/` | 39 | 10 | Voice agent tests — orchestrator, mute behavior, session management, TTS/STT providers |
| `unit/` | 33 | 6 | Pure unit tests — isolated function tests for utilities, config parsing, template rendering |
| `cli/` | 29 | 3 | CLI interface tests — help text, command registration, argument parsing, Typer app structure |
| `backend/` | 23 | 7 | Backend server tests — FastAPI routes, Pub/Sub workers, health checks |
| `e2e/` | 19 | 2 | End-to-end interactive tests — simulated interactive preflight, voice mode, full workflow flows |
| `db/` | 15 | 1 | Database tests — SQLite artifact storage, CRUD operations, migrations |
| `sync/` | 9 | 3 | Sync pipeline tests — Notion bidirectional sync, artifact serialization, conflict resolution |
| `admin/` | 8 | 3 | Admin console tests — dashboard API, project status, Kanban views |

## Configuration

Pytest is configured in `.agent/pyproject.toml`:

```toml
[tool.pytest.ini_options]
norecursedirs = [".git", ".venv", "venv", "build", "dist", "__pycache__", "src"]
```

The `src` directory is excluded to prevent pytest from accidentally importing and collecting source modules as tests.

A root `conftest.py` at `.agent/tests/conftest.py` provides:
- **`set_terminal_width`** (autouse) — forces `COLUMNS=1000` so Rich/Typer output assertions don't break due to terminal word wrapping.
- **`run_cli_command`** — provides a `CliRunner` fixture for Typer command invocation.

## Known Issues

### Full Suite Collection Hang

Running `uv run pytest .agent/tests` (the entire suite at once) may hang indefinitely during test collection. Each individual directory runs and passes correctly in isolation. The root cause is suspected to be a circular import or blocking fixture interaction that only triggers when all test modules are collected into a single session.

**Workaround**: Run directories individually using the loop shown above.

## Copyright

Copyright 2026 Justin Cook
