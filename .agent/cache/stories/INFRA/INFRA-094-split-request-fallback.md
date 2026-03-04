# INFRA-094: SPLIT_REQUEST Fallback for Runbook Generation

## State

COMMITTED

## Problem Statement

Even when the Forecast Gate passes, the Runbook Agent may generate an over-limit runbook that degrades implementation quality. There is no secondary defence to catch discrepancies between the heuristic forecast and the actual AI-generated plan. This is Layer 2 of the INFRA-089 defence-in-depth strategy.

## User Story

As a **developer using the agentic-dev framework**, I want **a SPLIT_REQUEST fallback that catches over-limit runbooks at generation time and saves decomposition suggestions** so that **no oversized runbook reaches the implementation phase**.

## Acceptance Criteria

- [ ] **AC-1 (Prompt Directive)**: Runbook Agent system prompt includes a Complexity Gatekeeper directive instructing the AI to emit `SPLIT_REQUEST` JSON if the runbook exceeds thresholds.
- [ ] **AC-2 (JSON Parse)**: Response containing `"SPLIT_REQUEST"` is detected and parsed.
- [ ] **AC-3 (Save)**: Decomposition suggestions saved to `.agent/cache/split_requests/{story_id}.json`.
- [ ] **AC-4 (Exit)**: CLI exits with code 2 and prints guidance message.
- [ ] **Negative**: Normal runbook response (no SPLIT_REQUEST) proceeds to file write.

## Non-Functional Requirements

- Compliance: Structured logging for SPLIT_REQUEST events (SOC2).
- Observability: Log with `story_id`, `reason`, `suggestion_count`.

## Linked ADRs

- ADR-005 (AI-Driven Governance Preflight)

## Linked Journeys

- JRN-064 — Forecast-Gated Story Decomposition (error path: SPLIT_REQUEST)

## Impact Analysis Summary

Components touched: `runbook.py`
Workflows affected: `/runbook`
Risks: AI may not reliably emit SPLIT_REQUEST JSON. Malformed JSON must be handled gracefully.

## Test Strategy

- Unit: Mock AI response with SPLIT_REQUEST JSON → parsed, saved, exit 2
- Unit: Normal runbook response → proceeds
- Unit: Malformed SPLIT_REQUEST JSON → graceful fallback (treat as normal runbook)

## Rollback Plan

Revert prompt and parsing changes in `runbook.py` and related tests. No migrations or config changes.

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0
