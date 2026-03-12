# INFRA-119: Squelching Unpredictable Behaviour (Input/Output Validation)

## State

REVIEW_NEEDED

## Problem Statement

Current heuristic-based ReAct parsing is brittle and prone to failure when Large Language Models (LLMs) generate non-standard or malformed outputs. This unpredictability leads to runtime crashes, broken execution chains, and high maintenance overhead for edge-case parsing logic.

## User Story

As a developer, I want to enforce strict JSON schemas for LLM outputs and implement an automatic retry/correction loop for malformed JSON so that the agent doesn't crash on syntax errors.

## Acceptance Criteria

- [ ] **Scenario 1**: Given an LLM response, When processed by the validation middleware, Then it must be successfully cast into Pydantic `AgentAction` or `Finish` BaseModels.
- [ ] **Scenario 2**: An automatic retry loop must be implemented that provides the specific validation error back to the LLM for self-correction (up to a defined maximum of attempts).
- [ ] **Negative Test**: System handles unrecoverable malformed JSON by logging a structured failure and gracefully terminating the current step instead of crashing the service.

## Non-Functional Requirements

- **Performance**: Validation and schema casting must add less than 50ms of overhead per inference cycle.
- **Security**: Ensure that schema validation prevents the execution of unexpected fields or injection patterns.
- **Compliance**: All retry attempts and validation errors must be logged in accordance with data retention policies.
- **Observability**: Track "Validation Failure Rate" and "Correction Success Rate" via telemetry dashboards.

## Linked Plan

- INFRA-118: Squelching Unpredictable Behaviour

## Linked ADRs

- ADR-012: Standardization on Pydantic for LLM I/O Validation

## Linked Journeys

- JRN-004: Agentic Reasoning Loop

## Impact Analysis Summary

Components touched:
- LLM Orchestration Layer
- Output Parsing Middleware
- Core Schema Library

Workflows affected:
- Agent decision-making and tool-calling sequences.

Risks identified:
- Increased latency during retry loops.
- Potential for "infinite loops" if retry logic is not properly capped.

## Test Strategy

- **Unit Testing**: Validate `AgentAction` and `Finish` models against a suite of valid and invalid JSON payloads.
- **Integration Testing**: Mock LLM responses to trigger the retry/correction loop and verify successful recovery.
- **Regression Testing**: Ensure existing tool-calling logic remains compatible with strict schema enforcement.

## Rollback Plan

In the event of systemic failures, the `ValidationMiddleware` can be bypassed via a feature flag (`ENABLE_STRICT_PARSING=false`), reverting the system to the legacy heuristic parser.

## Copyright

Copyright 2026 Justin Cook
