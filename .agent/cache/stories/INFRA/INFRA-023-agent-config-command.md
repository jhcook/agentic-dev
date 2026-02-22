# INFRA-023: Agent Config Command

## State

COMMITTED

## Problem Statement
Currently, configuring the agent requires manually editing YAML files (e.g., `.agent/etc/router.yaml`). This is error-prone and less convenient than a CLI interface. Users need a quick way to view and modify configuration settings, such as the active AI model or provider, directly from the command line.

## User Story
As a developer, I want to use `env -u VIRTUAL_ENV uv run agent config get` and `env -u VIRTUAL_ENV uv run agent config set` commands so that I can easily manage my agent configuration without manually editing YAML files.

## Acceptance Criteria
- [ ] **Scenario 1**: `env -u VIRTUAL_ENV uv run agent config set <key> <value>` updates the configuration in the appropriate file and persists it.
- [ ] **Scenario 2**: `env -u VIRTUAL_ENV uv run agent config get <key>` retrieves and displays the current value of a configuration key.
- [ ] **Scenario 3**: Support dot-notation for nested keys (e.g., `env -u VIRTUAL_ENV uv run agent config set models.gemini.deployment_id gemini-2.0-flash`).
- [ ] **Scenario 4**: `env -u VIRTUAL_ENV uv run agent config list` (or similar) displays all current configurations.
- [ ] **Negative Test**: System handles invalid keys or values gracefully (e.g., setting a non-existent key, or invalid type).

## Non-Functional Requirements
- **Performance**: Config updates should be immediate.
- **Security**: No secrets should be exposed in plain text output if possible (though keys in config are effectively cleartext currently).
- **Usability**: Command should provide helpful error messages for invalid keys.

## Linked ADRs
- N/A

## Impact Analysis Summary
- **Components touched**: CLI (`agent/cli.py`, `agent/commands/config.py`), Config Loader (`agent/core/config.py`).
- **Workflows affected**: Users changing config.
- **Risks identified**: corrupted config file if write fails; potential for user to set invalid config breaking the agent.

## Test Strategy
- Unit tests for `config set` and `config get` logic.
- Integration test ensuring `env -u VIRTUAL_ENV uv run agent config set` changes persist and are reflected in subsequent agent runs.

## Rollback Plan
- Revert the code changes.
- Manual restoration of config files if corrupted (users should backup manually, or we could add auto-backup).
