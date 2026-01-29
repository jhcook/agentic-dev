# ADR-016: CLI Output and Logging Standards

## Status

ACCEPTED

## Context

Agents and Linters often treat `print()` statements as "production code smells" (Rule T201), attempting to replace them with `logging.info()`.
In a CLI application, `print()` (or `rich.console.print`) is the correct way to communicate with the user. `logging` is for system diagnostics.
Confusing these leads to "Agent Drift" where useful user output is suppressed into logs.

## Decision

We formally distinguish between **User Output** and **System Logs**.

### 1. User Output

- **Purpose**: Information the user *needs* to see (Status, Prompts, Tables, Errors).
- **Mechanism**: `print()`, `typer.echo()`, or `rich.console.print()`.
- **Stream**: STDOUT / STDERR.
- **Agent Rule**: NEVER replace these with `logger` calls unless migrating to `rich`.

### 2. System Logs

- **Purpose**: Debugging, Tracing, Auditing, Internal State.
- **Mechanism**: `logging.info()`, `structlog`, `logger.debug()`.
- **Stream**: STDERR (usually), or Log File.
- **Verbosity**:
  - Default: `WARNING` only.
  - `-v`: `INFO`.
  - `-vv`: `DEBUG`.

## Consequences

- **Linter Config**: We must configure linters (`ruff`) to IGNORE `T201` (print found) in CLI command directories (`src/agent/commands`).
- **Agent Behavior**: Agents must check if a file is a CLI command before "fixing" prints.
