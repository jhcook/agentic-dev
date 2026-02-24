# NotebookLM CLI Authentication: Automated Authentication with Browser Cookies

Status: COMMITTED

## Problem Statement

Users are encountering issues authenticating the NotebookLM CLI due to Google's robot detection mechanisms when using interactive browser-based authentication. This slows down the user onboarding process and hinders automation workflows.

## User Story

As a NotebookLM CLI user, I want the ability to authenticate using browser cookies automatically extracted from my local machine, so that I can bypass Google's robot detection and streamline the authentication process for both interactive and automated workflows.

## Acceptance Criteria

- [ ] **Scenario 1**: Given the user provides the `--auto` flag, When the `agent mcp auth notebooklm` command is executed, Then the CLI attempts to automatically extract cookies from supported browsers on the user's machine.
- [ ] **Scenario 2**: Given the `--file <path>` flag, When the `agent mcp auth notebooklm` command is executed, Then the CLI attempts to authenticate using cookies from the file at `<path>`.
- [ ] **Scenario 3**: Given the `--no-auto-launch` flag, When the `agent mcp auth notebooklm` command is executed, Then the CLI skips the auto-launch of the browser for interactive authentication.
- [ ] **Scenario 4**: When cookies are successfully extracted via the `--auto` flag, the CLI should store the authentication token securely for subsequent commands.
- [ ] **Scenario 5**: Commands refactored for `async` communication (like `mcp` and `sync`) should function correctly without regression.
- [ ] **Scenario 6**: Given NotebookLM sync state is stored in the database, When calling `agent sync notebooklm --reset` or `--flush`, Then the local database index should be successfully purged (and remote notebook deleted for `--flush`).
- [ ] **Negative Test**: System handles the case where no supported browsers are found on the user's machine gracefully, informing the user to use other authentication methods.
- [ ] **Negative Test**: System handles the case where cookie extraction fails gracefully, providing informative error messages.

## Non-Functional Requirements

- **Performance**: Cookie extraction process should be reasonably fast.
- **Security**: Extracted cookies and authentication tokens must be stored securely to prevent unauthorized access.
- **Compliance**: Cookie extraction must comply with browser security policies and user privacy regulations.
- **Observability**: Log successful and failed authentication attempts with sufficient detail for debugging.

## Linked ADRs

- ADR-031: NotebookLM Cookie Authentication
- ADR-032: Async Refactoring for MCP Commands
- ADR-033: NotebookLM Database Caching and Reset/Flush Commands

## Linked Journeys

- JRN-063

## Impact Analysis Summary

Components touched:
- `agent mcp auth notebooklm` command
- Authentication logic
- Cookie extraction library (browser_cookie3)
- Configuration storage
- Async event loop integration for MCP connection pooling
- SQLite database caching layer for NotebookLM artifact synchronization state

Workflows affected:
- NotebookLM CLI authentication
- `agent sync notebooklm` operations (now async per ADR-032, with new `--reset` and `--flush` commands per ADR-033)
- `agent mcp run-tool notebooklm` execution (now async per ADR-032)

*Note: User-facing documentation (e.g., CLI help text, user guides) must be updated for the new `--auto`, `--file`, `--no-auto-launch`, `--reset`, and `--flush` flags.*

Risks identified:
- Browser compatibility issues.
- Potential for security vulnerabilities in cookie extraction.
- Reliance on external library (browser_cookie3) which may be subject to change.
- Multi-threading deadlocks related to improper `asyncio.run` usage within synchronous callers.

## Test Strategy

- **Unit/Integration Tests**:
  - Test cookie extraction logic explicitly to ensure it correctly falls back or errors when cookies are not found.
  - Test command argument parsing to ensure `--auto`, `--file`, and `--no-auto-launch` are correctly passed to handlers.
  - Test `async` connection capabilities when pulling NotebookLM state.
  - **New Requirement (ADR-033)**: Add integration tests for `agent sync notebooklm --reset` and `--flush` commands. These tests should assert the correct changes in the local database and mock the remote deletion for the flush command.

- **Journey Tests**:
  - Implement the end-to-end journey test in `test_infra_077.py` for the NotebookLM authentication flow and data syncing to ensure the user journey is validated (removing the stub).

- **Manual Testing/Security Audits**:
  - Verify `--auto` extracts cookies on a valid Chrome user profile.
  - Verify `--no-auto-launch` prevents the browser from opening.
  - Security audits to identify potential vulnerabilities in cookie extraction.

## Rollback Plan

Revert to the previous version of the CLI without the `--auto`, `--file`, and `--no-auto-launch` flags. This will require redeploying the older CLI version and updating any documentation.

## Copyright

Copyright 2026 Justin Cook
