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
- [ ] **Negative Test**: System handles the case where no supported browsers are found on the user's machine gracefully, informing the user to use other authentication methods.
- [ ] **Negative Test**: System handles the case where cookie extraction fails gracefully, providing informative error messages.

## Non-Functional Requirements

- **Performance**: Cookie extraction process should be reasonably fast.
- **Security**: Extracted cookies and authentication tokens must be stored securely to prevent unauthorized access.
- **Compliance**: Cookie extraction must comply with browser security policies and user privacy regulations.
- **Observability**: Log successful and failed authentication attempts with sufficient detail for debugging.

## Linked ADRs

- ADR-XXX (Placeholder, replace with actual ADR number if applicable)

## Linked Journeys

- JRN-063

## Impact Analysis Summary

Components touched:
- `agent mcp auth notebooklm` command
- Authentication logic
- Cookie extraction library (browser_cookie3)
- Configuration storage

Workflows affected:
- NotebookLM CLI authentication

Risks identified:
- Browser compatibility issues.
- Potential for security vulnerabilities in cookie extraction.
- Reliance on external library (browser_cookie3) which may be subject to change.

## Test Strategy

- Unit tests for cookie extraction logic.
- Integration tests for the `agent mcp auth notebooklm` command with different browsers.
- End-to-end tests to verify successful authentication and authorization with NotebookLM.
- Security audits to identify potential vulnerabilities.

## Rollback Plan

Revert to the previous version of the CLI without the `--auto`, `--file`, and `--no-auto-launch` flags. This will require redeploying the older CLI version and updating any documentation.

## Copyright

Copyright 2026 Justin Cook
