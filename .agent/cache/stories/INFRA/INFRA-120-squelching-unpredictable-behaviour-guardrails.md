# INFRA-120: Squelching Unpredictable Behaviour (Guardrails)

## State

COMMITTED

## Problem Statement

Automated tool-calling sequences can enter infinite recursive loops where an agent repeatedly calls the same tools without reaching a terminal state. This leads to excessive compute costs, latency, and unpredictable system behavior.

## User Story

As a developer, I want to enforce strict iteration limits and semantic/deterministic guardrails during execution so that I can prevent runaway recursive loops and ensure system stability.

## Acceptance Criteria

- [ ] **Scenario 1**: Given an active tool-calling session, When the `max_iterations` threshold (default: 10) is reached, Then the system must immediately terminate execution and return a structured "limit reached" error.
- [ ] **Scenario 2**: Loop interceptor logic must identify repeated tool calls with identical parameters within a single session and trigger an early termination.
- [ ] **Negative Test**: System handles execution termination gracefully by logging the state and returning a valid partial response rather than a timeout or unhandled exception.

## Non-Functional Requirements

- **Performance**: Guardrail checks must introduce less than 10ms of overhead per iteration.
- **Security**: Mitigates resource exhaustion attacks via recursive prompt injections.
- **Compliance**: All guardrail-triggered terminations must be recorded in the audit log.
- **Observability**: Expose metrics for `guardrail_interventions_total` to monitor frequency of aborted loops.

## Linked Plan

- INFRA-118: Squelching Unpredictable Behaviour

## Linked ADRs

- ADR-042 (Agent Execution Guardrails)

## Linked Journeys

- JRN-015 (Tool Integration and Execution)

## Impact Analysis Summary

**Components touched**: Agent Orchestrator, Execution Engine, Logging Service.
**Workflows affected**: LLM Inference pipeline, External Tool Dispatcher.
**Risks identified**: Potential for "false positives" where complex, legitimate multi-step tasks are truncated; requires configurable overrides per tool-type.

## Test Strategy

Verification will involve unit tests for the interceptor logic and integration tests using a "mock loop" tool designed to trigger recursive calls to ensure the termination logic fires correctly at the set threshold.

## Rollback Plan

Disable the guardrail logic via the `ENABLE_LOOP_GUARDRAILS` feature flag and revert to the previous `max_iterations` configuration in the orchestrator service.

## Copyright

Copyright 2026 Justin Cook
