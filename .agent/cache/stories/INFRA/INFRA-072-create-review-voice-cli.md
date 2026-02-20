# INFRA-072: Create `agent review-voice` CLI Command

## State

IN_PROGRESS

## Problem Statement

The `/review-voice` workflow is the only workflow with zero CLI backing. It instructs the agent to run a Python script (`fetch_last_session.py`), then manually analyze the conversation for latency, accuracy, tone, and interruption issues. This logic should be a proper CLI command.

## User Story

As a developer using `/review-voice`, I want an `agent review-voice` command that fetches the last voice session, runs AI analysis, and outputs structured UX feedback, so that voice session review is a single CLI invocation.

## Acceptance Criteria

- [ ] **AC1: Session Fetch**: `agent review-voice` executes `fetch_last_session.py` and captures the output.
- [ ] **AC2: AI Analysis**: The captured session history is sent to the AI with a prompt evaluating latency, accuracy, tone, and interruption.
- [ ] **AC3: Structured Output**: Output includes per-category ratings and concrete recommendations for `voice_system_prompt.txt` or `voice.yaml`.
- [ ] **AC4: No Session Handling**: If no active session is found, the CLI reports cleanly and exits 0.
- [ ] **AC5: Workflow Simplification**: `/review-voice` workflow is reduced to calling `agent review-voice`.
- [ ] **Negative Test**: Missing `fetch_last_session.py` script produces a clear error.

## Non-Functional Requirements

- **Observability**: Log session size and analysis duration.
- **Compliance**: New `voice.py` file must include Apache 2.0 license header.

## Linked ADRs

- ADR-025

## Linked Journeys

- JRN-061 (Voice Session Review Workflow)

## Impact Analysis Summary

Components touched: New `voice.py` command module, `main.py` registration, `review-voice.md` workflow
Workflows affected: `/review-voice`
Risks identified: Voice infrastructure may not be active in all environments; needs graceful degradation.

## Test Strategy

- **Unit test**: Verify session fetch subprocess call.
- **Unit test**: Verify AI prompt construction includes session content (using sample session fixture with realistic conversation turns).
- **Unit test**: Verify structured output includes per-category ratings (latency, accuracy, tone, interruption).
- **Unit test**: Verify graceful handling of missing script.

## Rollback Plan

Remove the new command. Workflow reverts to manual script execution.
