# ADR-034: Use `uv` for Isolated Package Execution

## Status

ACCEPTED

## Context

The Agent CLI needs to execute third-party packages that carry elevated security risk (e.g., `browser-cookie3` for extracting session cookies) or that have heavy/conflicting dependency trees. Installing these packages directly into the main virtual environment introduces supply-chain risk, version conflicts, and exposes the runtime to potentially malicious transitive dependencies.

`uv` (from Astral) is already a system-level dependency used to manage the Agent CLI's virtual environment and run `pytest`. It provides a `uv run --with <package>` command that downloads and executes a pinned package in a temporary, isolated environment without modifying the project's virtual environment.

## Decision

1. **`uv` is a required system dependency** for running the Agent CLI. It must be available on `$PATH`.
2. **Risky or optional packages** (e.g., `browser-cookie3`) will NOT be listed as direct dependencies in `pyproject.toml`. Instead, they will be invoked via `uv run --with <package>==<pinned-version> python -c "<script>"` in an isolated subprocess.
3. **Version pinning is mandatory** — any package executed via `uv run --with` must specify an exact version (e.g., `browser-cookie3==0.20.1`) to prevent supply-chain attacks from automatic version bumps.
4. **Output from isolated execution** must be structured (JSON) and validated by the calling code. Unstructured output must not be trusted.

## Consequences

**Positive:**
- Isolates risky dependencies from the main runtime, reducing supply-chain attack surface.
- Prevents version conflicts between optional packages and core dependencies.
- Enables pinned, reproducible execution of third-party tools without polluting `pyproject.toml`.
- Aligns with the existing `uv`-based development workflow.

**Negative:**
- Adds `uv` as a hard system dependency (must be installed separately from the Python package).
- Slightly slower execution due to the subprocess overhead and potential package download on first run.
- Developers must be aware of the `uv run --with` pattern when adding new risky integrations.

## Supersedes

None

## Copyright

Copyright 2026 Justin Cook
