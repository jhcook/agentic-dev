# INFRA-078: Preflight Remediation for NotebookLM Authentication

## State

COMMITTED

## Problem Statement

The INFRA-077 story for NotebookLM CLI authentication failed the AI Governance Preflight checks due to multiple blocking issues across Security, Compliance, Product, Architecture, and Observability domains, primarily stemming from the `--auto` flag's insecure extraction and storage of browser cookies and lack of explicit user consent.

## User Story

As a developer using the `agentic-dev` CLI, I want the NotebookLM authentication flow to be secure, compliant, observable, and fully tested so that I can authenticate without compromising security or violating GDPR consent and architectural standards.

## Acceptance Criteria

- [ ] **Prompt for Consent**: The `--auto` flag must explicitly ask the user for consent before extracting cookies from local browsers using `browser-cookie3`.
- [ ] **Secure Storage**: Extracted cookies must be stored securely using the `agent.core.secrets.SecretManager` instead of a plaintext `auth.json` file.
- [ ] **Dependency Pinning**: The `browser-cookie3` dependency must be pinned to exactly version `0.20.1` during runtime execution to prevent supply-chain attacks.
- [ ] **Flag Documentation**: The `--file`, `--no-auto-launch`, and `--auto` flags must be documented in the README and CHANGELOG.
- [ ] **Fix File Input**: The `--file` flag must accept a file path (`str`) rather than a boolean.
- [ ] **Synchronize Tool Names**: The backend NotebookLM sync tools must use the correct prefix (`mcp_notebooklm_`) as defined by the MCP server, and the integration test must assert this.
- [ ] **Observability**: The authentication flow must use structured logging (`logger`) and include OpenTelemetry tracing spans.
- [ ] **ADR Creation**: An ADR must be written to formalize the decision to use automated cookie extraction with user consent and secure storage.
- [ ] **Preflight Pass**: The `agent preflight` command must pass for these changes.

## Non-Functional Requirements

- Performance
- Security
- Compliance
- Observability

## Linked ADRs

- ADR-0002

## Linked Journeys

- JRN-063

## Impact Analysis Summary

Components touched: `agent/commands/mcp.py`, `agent/sync/notebooklm.py`, and `test_notebooklm_sync.py`.
Workflows affected: NotebookLM authentication for syncing files.
Risks identified: Potential for PII exposure if cookies are logged or leaked during unhandled exceptions. Mitigated by strict error handling and SecretManager usage.

## Test Strategy

How will we verify correctness?
- Integration tests in `.agent/tests/integration/test_mcp_auth.py` will mock the subprocess to verify `browser-cookie3` JSON parsing and `SecretManager` storage.
- Tests will ensure that negative cases (like user consent rejection and JSON decode errors) are handled gracefully without exposing PII.
- The `--no-auto-launch`, `--file`, and `--auto` flows will be covered.
- The "Synchronize Tool Names" acceptance criterion will be verified by `test_notebooklm_sync_execution` in `.agent/tests/integration/test_notebooklm_sync.py`, ensuring all tool calls use the `mcp_notebooklm_` prefix.

## Rollback Plan

How do we revert safely?

## Copyright

Copyright 2026 Justin Cook
