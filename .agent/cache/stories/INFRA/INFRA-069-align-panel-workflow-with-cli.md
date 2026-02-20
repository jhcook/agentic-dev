# INFRA-069: Align `/panel` Workflow with `agent panel` CLI

## State

IN_PROGRESS

## Problem Statement

The `/panel` workflow states: "This workflow mimics the behavior of the `agent panel` CLI command but executes via the Agent directly." This is a clear duplication — the workflow re-implements what the CLI command already does. The workflow should call `agent panel` instead of duplicating its logic.

## User Story

As a developer using `/panel`, I want the workflow to call `agent panel` so that consultative governance sessions are driven by the CLI and I get consistent results regardless of whether I use the slash command or the CLI directly.

## Acceptance Criteria

- [ ] **AC1: Parity**: `agent panel` output is the **source of truth** for the consultation report format. The `/panel` workflow is updated to match the CLI's output, not the other way around.
- [ ] **AC2: Story Context**: `agent panel --story <ID>` reads the story file and includes it in the consultation context.
- [ ] **AC3: Advisory Mode**: `agent panel` output uses "Advice" and "Recommendations" framing (not BLOCK/PASS), matching the workflow's consultative intent.
- [ ] **AC4: Workflow Simplification**: `/panel` workflow is reduced to calling `agent panel --story <ID>`, with a "See Also: `agent panel --help`" reference.
- [ ] **Negative Test**: `agent panel` with no staged changes reports cleanly.

## Non-Functional Requirements

- **Consistency**: Output format must be identical whether invoked via CLI or workflow.

## Linked ADRs

- ADR-025

## Linked Journeys

- JRN-058 (Panel Consultation Workflow)

## Impact Analysis Summary

Components touched: `check.py` (panel command), `panel.md` workflow
Workflows affected: `/panel`
Risks identified: The existing `agent panel` command may already have full parity — needs verification before any code changes.

## Test Strategy

- **Manual**: Compare output of `agent panel` vs the workflow's expected format.
- **Unit test**: Verify `agent panel --story` loads story context.

## Rollback Plan

Revert workflow changes. CLI command is unaffected.
