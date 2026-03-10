# INFRA-105: Decompose Onboard Command

## State

ACCEPTED

## Parent Plan

INFRA-099

## Problem Statement

The `commands/onboard.py` module has grown to 1,060 LOC. It conflates the CLI surface (Typer command definitions, Rich console output) with the step-by-step onboarding logic (dependency checks, `.env` setup, `.gitignore` configuration, secrets vault initialisation, Git hooks installation). This makes it impractical to re-use individual onboarding steps in automated contexts (e.g., CI bootstrap) and difficult to test steps in isolation.

## User Story

As a **Backend Engineer**, I want to **decompose the monolithic onboard command into a thin CLI facade and a dedicated step-library module** so that **each onboarding step is independently callable and testable, the 500 LOC ceiling is respected, and automated bootstrap scripts can invoke steps without launching the full CLI.**

## Acceptance Criteria

- [x] **AC-1**: `commands/onboard.py` is reduced to a thin Typer CLI facade ≤500 LOC that calls step functions from `core/onboard/steps.py`.
- [x] **AC-2**: `core/onboard/steps.py`, `settings.py`, and `integrations.py` contain all step implementations: `check_dependencies`, `setup_env_file`, `configure_gitignore`, `init_secrets_vault`, `install_git_hooks`, and any helper utilities — ≤500 LOC each.
- [x] **AC-3**: `core/onboard/__init__.py` re-exports the public step API.
- [x] **AC-4**: Step functions accept a `prompter: Prompter` parameter rather than creating their own, enabling dependency injection for testing.
- [x] **AC-5**: All existing tests in `tests/commands/test_onboard.py` pass without modification.
- [x] **AC-6**: No circular imports — `python -c "import agent.cli"` succeeds.
- [x] **AC-7**: New unit tests in `tests/core/onboard/test_steps.py` covering each step function with mocked filesystem and subprocess calls.
- [x] **AC-8**: All new modules include PEP-484 type hints and PEP-257 docstrings.
- [x] **Negative Test**: `check_dependencies` logs a clear warning and returns `False` (rather than raising) when a required binary is missing from `PATH`.

## Non-Functional Requirements

- **Performance**: Onboarding step execution time unchanged.
- **Security**: Secret vault initialisation logic must not log raw keys; `get_secret_manager` usage preserved.
- **Compliance**: N/A.
- **Observability**: OpenTelemetry spans from `tracer = trace.get_tracer(__name__)` preserved in `commands/onboard.py`; steps emit structured log lines.

## Linked ADRs

- ADR-041: Module Decomposition Standards

## Linked Journeys

- JRN-014: Create `agent onboard` CLI command

## Impact Analysis Summary

- **Components touched**: `commands/onboard.py`, `commands/secret.py`, `core/auth/utils.py`, `core/onboard/steps.py`, `core/onboard/settings.py`, `core/onboard/integrations.py`, `core/onboard/prompter.py`, `core/onboard/__init__.py`, `tests/cli/test_onboard_e2e.py`, `tests/cli/test_onboard_unit.py`, `tests/core/auth/test_utils.py`, `tests/core/onboard/test_steps.py`, `tests/core/onboard/test_settings.py`, `tests/core/onboard/test_integrations.py`.
- **Workflows affected**: `agent onboard` command, any CI bootstrap script invoking onboarding steps.
- **Risks identified**: `check_dependencies` uses `shutil.which` and `subprocess` — mocking strategy in tests must be consistent across old and new locations.
- **Out-of-Scope Changes**: Unrelated updates to `README.md`, `pyproject.toml`, `.agent/etc/agent.yaml`, `.agent/tests/integration/test_preflight_report.py`, and `src/agent/main.py` to address Python 3.13 incompatibility, as well as `src/agent/core/implement/orchestrator.py` to address regex parsing bugs for code blocks.

## Test Strategy

- **Regression**: Run existing `tests/commands/test_onboard.py` without modification; 100% pass rate required.
- **Unit Testing**: New tests for each step function using `unittest.mock.patch` for filesystem and subprocess calls.
- **Integration**: Run `agent onboard` in a temporary directory to verify the full onboarding flow completes successfully end-to-end.

## Rollback Plan

- Revert the feature branch to the previous stable commit on `main`.
- Restore `commands/onboard.py` from git history and remove the `core/onboard/` package.

## Copyright

Copyright 2026 Justin Cook
