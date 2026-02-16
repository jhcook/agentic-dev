# ADR-028: Typer Synchronous CLI Architecture

## State

ACCEPTED

## Context

The Agent CLI is built on [Typer](https://typer.tiangolo.com/), which is a synchronous CLI framework. Typer command functions are **synchronous Python functions** — they do not run inside an `asyncio` event loop.

The AI Governance Council has repeatedly flagged `subprocess.run()` and `subprocess.Popen()` calls in Typer commands as "blocking the event loop" and recommended migrating to `asyncio.create_subprocess_exec()`. This is incorrect — there is no event loop to block.

## Decision

**`subprocess.run()` and `subprocess.Popen()` are the correct APIs for Typer CLI commands.**

### Rules for Governance Reviewers

1. **Typer commands are synchronous**: All functions registered via `app.command()` in `agent/main.py` execute in a standard synchronous call stack. There is no `asyncio` event loop.
2. **`subprocess.run()` is appropriate**: For commands that need to execute external processes (e.g., `pytest`, `git diff`, `git add`), blocking subprocess calls are the correct pattern.
3. **`subprocess.Popen()` with line buffering is appropriate**: For commands that stream output (e.g., test execution with real-time progress), `Popen` with `iter(proc.stdout.readline, "")` is the standard synchronous streaming pattern.
4. **Do NOT recommend `asyncio` alternatives**: `asyncio.create_subprocess_exec()` requires an async context. Typer does not provide one. Wrapping Typer commands in `asyncio.run()` would add unnecessary complexity.

### Scope

This ADR applies to all files in `.agent/src/agent/commands/`:

- `check.py` — `preflight()`, `impact()`, `panel()`
- `workflow.py` — `commit()`, `pr()`
- Any future Typer command that calls subprocess

### When Async IS Appropriate

If the Agent CLI adds a web server, background worker, or real-time streaming component (e.g., FastAPI, WebSocket), those components should use async subprocess calls. This ADR does not apply to non-CLI execution contexts.

## Alternatives Considered

- **Migrating to async CLI framework (e.g., `asyncclick`)**: Adds complexity and breaks the existing Typer ecosystem (auto-generated help, type annotations, shell completion).
- **Wrapping sync commands in `asyncio.run()`**: Unnecessary overhead that gains nothing for a sequential CLI tool.
- **Using `concurrent.futures.ThreadPoolExecutor`**: Useful for parallel I/O but not needed for sequential `git` and `pytest` calls.

## Consequences

- **Positive**: Eliminates a recurring class of false-positive governance blocks.
- **Positive**: Provides clear guidance that sync subprocess is intentional, not an oversight.
- **Negative**: If the CLI is ever embedded in an async context (e.g., agent-as-a-service), subprocess calls will need refactoring — but that would be a new ADR.
