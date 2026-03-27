# INFRA-167: CLI Integration and Observability

## State

COMMITTED

## Problem Statement

The current `agent new-runbook` command operates sequentially and lacks transparency, making it difficult for users to track progress on long-running tasks or monitor the costs associated with LLM token consumption. Additionally, users require a way to maintain backward compatibility during the transition to new generation logic.

## User Story

As a **DevOps Engineer**, I want **enhanced execution controls and real-time feedback for runbook generation** so that **I can complete tasks faster, monitor resource consumption, and maintain workflow stability.**

## Acceptance Criteria

- [ ] **Scenario 1 (Efficiency & Feedback)**: Given a request for a complex runbook, When I execute `agent new-runbook`, Then tasks should execute in parallel with a live progress bar displayed in the terminal.
- [ ] **Scenario 2 (Cost Transparency)**: When the command completes, Then a summary of total tokens consumed (input and output) must be logged to the console and stored in the observability backend.
- [ ] **Scenario 3 (Backward Compatibility)**: Given the need for the previous generation logic, When I pass the `--legacy-gen` flag, Then the system must bypass the new logic and use the v1 generation engine.
- [ ] **Negative Test**: System handles **network timeouts or partial execution failures** gracefully by reporting which specific parallel task failed while preserving logs for completed tasks.

## Non-Functional Requirements

- **Performance**: Parallel execution should reduce total runbook generation time by at least 40% for multi-step runbooks.
- **Security**: Token usage logs must not contain sensitive prompt data or PII.
- **Compliance**: Ensure all logged metrics adhere to internal data retention policies.
- **Observability**: Integration with OpenTelemetry for tracking command execution latency and token metrics.

## Linked ADRs

- ADR-012: Parallel Task Execution Framework
- ADR-015: Observability and Token Tracking Schema

## Linked Journeys

- JRN-004: Automated Runbook Generation

## Impact Analysis Summary

- **Components touched**: CLI Parser, Agent Execution Engine, Logging/Observability Module.
- **Workflows affected**: Runbook creation lifecycle.
- **Risks identified**: Potential for rate-limiting by LLM providers due to parallel requests; race conditions in progress bar rendering.
- **Out-of-scope changes made during implementation**:
  - `implement.py` — Docstring gate demoted from hard-block to warning for `[NEW]` files; test files exempted (tracked in INFRA-173).
  - `runbook.py` — S/R fuzzy-match threshold raised 0.6→0.80 to prevent over-broad auto-corrections on critical files.
  - `runbook_generation.py` — Syntax error removed (garbled class stub injected by prior S/R apply).
  - `sr_validation.py` — Adjusted as part of chunked-pipeline stabilisation.
  - `prompts.py` — Updated skeleton and block prompts for two-phase generation.
  - `.markdownlint.yaml` — Disabled `MD001` (heading increment), `MD004` (list marker style), `MD030` (spaces after list markers), and `MD009` (trailing spaces) for AI-generated runbook content.
  - INFRA-173 story created to formally track the verbatim-apply silent-drop fix.

## Test Strategy

- **Unit Testing**: Validate logic for the `--legacy-gen` flag and token calculation utility.
- **Integration Testing**: Verify parallel execution using mocked LLM responses.
- **End-to-End Testing**: Execute the CLI against a staging environment to verify progress bar UI and telemetry export.

## Rollback Plan

- **Short-term**: Use `--legacy-gen` to bypass new logic.
- **Long-term**: Revert CLI binary to the previous stable version (v1.x.x) via the package manager.

## Copyright

Copyright 2026 Justin Cook