# ADR-099: Top-Level Test Directory Layout and PYTHONPATH=src Configuration

## Status

ACCEPTED

## Context

During INFRA-143 (Restoring and Fixing Test Suites), the agent framework test suite was
restructured from a co-located layout (tests scattered inside `src/agent/*/tests/`) to a
single top-level directory at `.agent/tests/`. This change was made to:

1. Align with standard Python project conventions (PEP 517 / `src` layout).
2. Prevent test-module import shadowing: when tests lived inside `src/`, pytest would
   sometimes resolve `agent.*` imports from the test tree rather than the installed package.
3. Enable clean `pytest --rootdir=.agent` invocations without `sys.path` hacks.
4. Allow heavy test suites (`voice/`, `backend/`, `integration/`, `e2e/`) to be excluded
   from the preflight loop via `--ignore` flags without modifying `src/`.

The INFRA-158 branch co-commits the restoration of journey test files (`tests/journeys/`)
and command test files (`tests/commands/`) that complete this layout, and formalises the
configuration in `pyproject.toml` and `agent.yaml`.

## Decision

The canonical test directory for all agent framework tests is `.agent/tests/`, mirroring
the `src/` layout:

```
.agent/
├── src/
│   └── agent/           # installable package (PYTHONPATH=src)
└── tests/
    ├── commands/        # CLI command tests
    ├── core/            # core module tests
    ├── journeys/        # JRN-NNN regression tests
    ├── unit/            # pure unit tests
    ├── sync/            # Notion sync tests
    ├── voice/           # voice pipeline tests (excluded from preflight)
    ├── backend/         # FastAPI backend tests (excluded from preflight)
    ├── integration/     # integration tests (excluded from preflight)
    └── e2e/             # end-to-end tests (excluded from preflight)
```

**`PYTHONPATH=src`** is set in `pyproject.toml` under `[tool.pytest.ini_options]` so that
`import agent` resolves to `src/agent/` in all pytest invocations without requiring the
package to be installed in editable mode.

**Preflight scope**: The CI preflight loop (governed by `agent.yaml`) explicitly ignores
`tests/voice`, `tests/backend`, `tests/integration`, and `tests/e2e`. These directories
import `torch`, `FastAPI`, and other heavy dependencies at module-collection time and cause
OOM kills when combined with the framework test suite in a single `pytest` process. They
are delegated to dedicated CI pipeline stages.

## Consequences

- All new tests MUST be placed in `.agent/tests/<category>/` — never inside `src/`.
- The `src/` directory contains only importable package code; no test files.
- `pytest` is always invoked with `PYTHONPATH=src` (set in `pyproject.toml` or the shell).
- Heavy suites are tested in isolation outside the preflight loop.
- Developers cloning the repo can run `pytest .agent/tests/` without additional setup.

## References

- INFRA-143: Restoring And Fixing Test Suites
- INFRA-158: Back-Populate Story ADRs and Journeys from Runbook (co-committed test files)
- `.agent/pyproject.toml` — `pythonpath = ["src"]` under `[tool.pytest.ini_options]`
- `.agent/etc/agent.yaml` — preflight `--ignore` flags for heavy suites
