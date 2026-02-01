# ADR-017: Agent CLI Command Governance

## Status

ACCEPTED

## Context

The `agent` CLI is the primary interface for this repository. Recently, regressions have occurred where commands were incorrectly wired or broken during refactors (e.g., `agent sync` pointing to a non-existent file).
Currently, there is no single source of truth for "what commands must exist", making it easy to accidentally remove or break functionality without tests catching it immediately.

## Decision

We will implement a stricter governance model for the Agent CLI:

### 1. The Command Registry

We define a canonical "Command Registry" (conceptually). This is enforced by:

- **Smoke Tests**: A comprehensive suite of smoke tests (e.g., `tests/smoke_commands.sh`) that iterates through *every* supported command to verify it runs (at least `--help`).
- **Unit Tests**: `tests/test_cli_structure.py` (or similar) must explicitly list expected commands and assert they constitute the `app` object.

### 2. No "Implicit" Commands

- All commands must be explicitly registered in `src/agent/main.py`.
- No dynamic loading of an entire directory without an explicit allowlist.

### 3. Change Control

- **New Commands**: Must be added to the Smoke Test suite *before* the Story is verified.
- **Removed Commands**: Deprecation period preferred. If immediate removal, MUST serve a clear error message or redirect for at least one version if possible, otherwise just hard break with clear Changelog entry.
- **Modifying Wiring**: Any refactor of `main.py` wiring requires running the full Smoke Test suite.

### 4. Authentication Safety

- Commands interacting with remote backends MUST reuse the standard `with_creds` decorator from `agent.core.auth.decorators`.
- It is forbidden to implement ad-hoc checks for `AGENT_USERNAME` inside individual command modules.

## Consequences

- **Reliability**: Regressions in top-level commands become "Stop the Line" failures in CI.
- **Visibility**: It is clear what the Agent *can* do.
- **Maintenance**: Adding a command requires slightly more friction (updating tests), which is intentional to prevent bloat.

## Current Registry (Snapshot)

*As of Feb 2026. This list is enforced by `tests/smoke_commands.sh`.*

### Core Workflow

- `new-story`
- `new-plan`
- `new-runbook`
- `new-adr`
- `implement`
- `pr`
- `commit`

### Governance & Check

- `preflight`
- `impact`
- `panel`
- `lint`
- `audit`
- `validate-story`
- `run-ui-tests`

### Infrastructure & Config

- `sync` (pull, push, status, scan, delete)
- `onboard`
- `query`
- `config` (subcommands...)
- `secret` (subcommands...)
- `admin` (subcommands...)
- `mcp` (subcommands...)

### Utilities

- `list-stories`
- `list-plans`
- `list-runbooks`
- `list-models`
- `match-story`
