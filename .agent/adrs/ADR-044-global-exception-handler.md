# ADR-044: Global Exception Handler at CLI Entry Point

## Status

ACCEPTED

## Date

2026-03-19

## Context

All `agent` subcommands previously propagated unhandled Python exceptions directly
to the terminal as full tracebacks — sometimes 30+ lines deep through third-party
HTTP client internals (e.g., an `httpx.ReadTimeout` surfacing through the httpcore
transport stack).  This provided no actionable guidance to the user and cluttered
the terminal with noise unrelated to the actual failure.

The root cause: `pyproject.toml` pointed the `agent` script directly at
`agent.main:app` (a `typer.Typer` instance), which has no top-level exception
boundary beyond `SystemExit`.

## Decision

Introduce a `main()` wrapper function in `agent/main.py` that wraps `app()` with
a structured exception boundary:

```python
def main() -> None:
    try:
        app()
    except SystemExit:
        raise          # typer.Exit / typer.Abort — pass through normally
    except KeyboardInterrupt:
        typer.echo("\n[Interrupted]", err=True)
        sys.exit(130)
    except Exception as exc:
        verbose = os.environ.get("AGENT_VERBOSE", "0") not in ("0", "")
        if verbose:
            traceback.print_exc()
        else:
            typer.echo(f"❌ {type(exc).__name__}: {exc}", err=True)
            typer.echo("   Run with -v for full traceback.", err=True)
        sys.exit(1)
```

`pyproject.toml` entry point updated from `agent.main:app` to `agent.main:main`.

## Consequences

### Positive

- Every `agent` command produces a **clean one-liner** on unhandled failure:
  `❌ TimeoutError: AI request to gemini timed out after 180s. Retry with: --timeout 300`
- Debug output is **opt-in** via `-v` or `AGENT_VERBOSE=1`, keeping normal operation
  terminal-clean.
- `KeyboardInterrupt` (Ctrl-C) exits cleanly with code 130 instead of printing
  a traceback.
- `SystemExit`/`typer.Exit` pass through unmodified — existing exit-code contracts
  are preserved.

### Negative / Risks

- Any exception not yet producing a meaningful `str()` representation will still
  show a terse but potentially cryptic one-liner.  Mitigated by domain-specific
  exception types (e.g., `TimeoutError`) that are caught closer to the source and
  given descriptive messages before propagating.
- The `main()` wrapper only applies to the installed CLI entry point.  Code called
  via `python -m agent` or direct import is unaffected — those paths already handle
  exceptions individually.

## Linked Story

INFRA-140 (AC-R14, AC-R15)

## Copyright

Copyright 2026 Justin Cook
