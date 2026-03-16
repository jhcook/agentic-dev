# INFRA-149: Schema Validation CLI Gate

## State

COMMITTED

## Problem Statement

Currently, runbooks are written to disk regardless of their structural integrity. This delays error detection until the `implement` phase, resulting in failed execution workflows and the persistence of invalid artifacts in the workspace.

Parent: INFRA-147

## User Story

As a **DevOps Engineer**, I want **the CLI to validate runbook schemas before file I/O operations** so that **I receive immediate feedback on structural errors and prevent invalid runbooks from entering the pipeline.**

## Acceptance Criteria

- [ ] **Scenario 1**: Given an AI-generated runbook string, When the `new-runbook` command is executed, Then the system must call `validate_runbook_schema()` and only write to disk if validation passes.
- [ ] **Scenario 2**: When using the `--apply` logic in `agent/commands/panel.py`, the system must intercept the runbook and perform a schema check before proceeding with the application.
- [ ] **Scenario 3**: Validation errors must be processed by a "Validation Error Formatter" that maps Pydantic `ValidationError` objects to human-readable CLI output, including line numbers and step indices.
- [ ] **Negative Test**: System handles **structurally invalid YAML/JSON** by displaying the formatted error and exiting with a **non-zero status code** without writing/updating files.

## Non-Functional Requirements

- **Performance**: Schema validation must add <150ms overhead to the command execution.
- **Security**: Validation logic must remain local to prevent leaking runbook contents to external validators.
- **Compliance**: Ensure all generated runbooks strictly adhere to the defined organizational JSON Schema.
- **Observability**: Validation failures should be logged to `stderr` to distinguish from standard process output.

## Linked ADRs

- ADR-014: Standardized Runbook Schema
- ADR-022: CLI Error Handling Strategy

## Linked Journeys

- JRN-003: Automated Runbook Generation
- JRN-007: Manual Runbook Application

## Impact Analysis Summary

**Components touched:**
- `agent/commands/runbook.py`
- `agent/commands/panel.py`
- New utility: `agent/utils/validation_formatter.py`

**Workflows affected:**
- Runbook creation (`new-runbook`)
- Panel application (`--apply`)

**Risks identified:**
- Potential for "breaking" legacy runbooks that do not meet new schema strictness.
- AI-generated content may require prompt tuning if validation failure rates increase.

## Test Strategy

- **Unit Tests**: Verify the `Validation Error Formatter` correctly parses complex Pydantic nested errors.
- **Integration Tests**: Mock `validate_runbook_schema()` to return success/fail and verify CLI exit codes and file I/O behavior.
- **E2E**: Execute `new-runbook` with a deliberately malformed prompt to ensure the gate blocks the write.

## Rollback Plan

Revert commits to `agent/commands/` to restore previous behavior where files are written without a validation gate. No database migrations are required.

## Copyright

Copyright 2026 Justin Cook
