# INFRA-071: Add Panel Consultation to `agent new-journey`

## State

COMMITTED

## Problem Statement

The `/journey` workflow has two stages: (1) scaffold via `agent new-journey`, and (2) a manual panel consultation where the agent adopts each governance role and reviews the journey. Step 2 is valuable but not encapsulated in the CLI — it requires the agent to manually read `agents.yaml`, adopt each role, and provide commentary.

## User Story

As a developer using `/journey`, I want `agent new-journey --panel` to automatically run a consultative panel review of the generated journey, so that governance feedback is integrated into journey creation without manual agent orchestration.

## Acceptance Criteria

- [ ] **AC1: Panel Flag**: `agent new-journey <ID> --ai --panel` generates a journey AND runs a panel consultation.
- [ ] **AC2: Inline Feedback**: Panel feedback is appended to the journey YAML as comments or a separate `panel_feedback` field.
- [ ] **AC3: Role Coverage**: All roles from `agents.yaml` are represented in the consultation.
- [ ] **AC4: Workflow Simplification**: `/journey` workflow Step 3 is replaced with a note to use `--panel`.
- [ ] **Negative Test**: `--panel` without `--ai` produces a clear error (panel requires AI-generated content to review).

## Non-Functional Requirements

- **Performance**: Panel consultation adds < 60s to journey creation.

## Linked ADRs

- ADR-025
- ADR-024 (Journeys as prerequisites)

## Linked Journeys

- JRN-060 (Journey Creation Workflow)

## Impact Analysis Summary

Components touched: `journey.py`, `journey.md` workflow
Workflows affected: `/journey`
Risks identified: Token budget for panel consultation with full journey content.

## Test Strategy

- **Unit test**: Verify `--panel` triggers AI consultation.
- **Unit test**: Verify `--panel` without `--ai` fails with clear error.

## Rollback Plan

Remove `--panel` flag. Journey creation returns to current behavior.
