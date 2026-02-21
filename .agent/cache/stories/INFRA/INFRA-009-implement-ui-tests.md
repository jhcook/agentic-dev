# INFRA-009: Implement UI Tests Runner

## Parent Plan
INFRA-008

## State
COMMITTED

## Problem Statement
The `env -u VIRTUAL_ENV uv run agent run-ui-tests` command is currently a stub. We have decided to standardize on **Maestro** for UI testing because its YAML flows are agent-friendly and support both mobile and web. We need the CLI to support executing these flows.

## User Story
As a developer, I want to run `env -u VIRTUAL_ENV uv run agent run-ui-tests [story-id]` so that I can automatically execute the Maestro flows (`.yaml`) associated with my feature.

## Acceptance Criteria
- [ ] Command `env -u VIRTUAL_ENV uv run agent run-ui-tests` checks for the presence of the `maestro` CLI.
- [ ] It looks for Maestro flows (`.yaml` files) in `tests/ui/` or `.maestro/`.
- [ ] It executes the flows using `maestro test <flow.yaml>`.
- [ ] It supports filtering checks found in the files (if applicable).
- [ ] Returns proper exit code based on Maestro's output.

## Non-Functional Requirements
- **Performance**: Should scan directories in under 1 second for standard repo sizes.
- **Security**: Must sanitize logs to avoid leaking PII from test outputs.
- **Usability**: Provide clear error messages if Maestro is missing.

## Rollback Plan
- Revert changes to `check.py` to restore the stub.
- Remove `README.md` entries.

## Impact Analysis Summary
Components touched: `agent/commands/check.py`, `README.md`, `.agent/tests/commands/`
Workflows affected: Local Development, CI/CD.
Risks identified: Requires `maestro` CLI installation.
Breaking Changes: None.

## Test Strategy
- Create a dummy `login_flow.yaml` in `tests/ui`.
- Run `env -u VIRTUAL_ENV uv run agent run-ui-tests`.
- Verify `maestro` is invoked and reports status.
