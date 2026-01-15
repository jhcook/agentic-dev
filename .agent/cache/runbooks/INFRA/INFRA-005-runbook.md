# INFRA-005: Global and Path-Based Linting

Status: ACCEPTED

## Goal Description
Refactor `agent lint` to support scanning arbitrary paths and the entire repository (`--all`). It should dispatch to the correct linter (`ruff` or `shellcheck`) based on file extension and operate on the provided path (or current working directory), rather than hardcoded internal paths.

## Panel Review Findings
{panel_checks}

## Implementation Steps
### Agent Core
#### [MODIFY] .agent/src/agent/commands/lint.py
- Refactor `get_changed_files` to be more generic `get_files_to_lint(path: Path, all: bool, base: str)`.
- Update `lint` command signature to accept `path` argument.
- Implement logic to walk the directory tree if `all` or a directory path is provided.
- Implement linter dispatch logic:
    - `*.py` -> `ruff`
    - `*.sh` -> `shellcheck`
    - `*.js`, `*.jsx`, `*.ts`, `*.tsx` -> `eslint` (via `npm` or `node_modules`).
- For JS/TS, implement logic to find the nearest `package.json` and run `npm run lint` if a script exists, or fall back to `npx eslint`.
- Ensure `ruff`, `shellcheck`, and `eslint` are called with the list of discovered files.

## Verification Plan
### Automated Tests
- [ ] `agent lint --all` passes on the repo.
- [ ] `agent lint .agent/src` passes.

### Manual Verification
- [ ] `cd web && agent lint` (should scan web dir).
- [ ] `agent lint --all` from root covers `.agent` and any web/mobile directories.
- [ ] Verify `agent lint` correctly invokes `eslint` for TS files.

## Definition of Done
### Documentation
- [ ] CHANGELOG.md updated

### Observability
- [ ] Logs are structured and free of PII

### Testing
- [ ] Unit tests passed
