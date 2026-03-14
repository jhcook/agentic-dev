# INFRA-136: Execution Tracing and Scope Guardrails with Langfuse

## State

DRAFT

## Problem Statement

The `agent implement` loop has no structural mechanism to prevent the agent from modifying files outside the runbook's declared scope. Implementation steps can silently touch, refactor, or delete files that were never mentioned in the runbook's "Targeted File Contents" section. This has resulted in unintentional removal of features and un-asked-for modifications that are only caught (if at all) by `agent preflight` — too late in the pipeline.

## User Story

As a **developer**, I want **the implementation loop to be traced and scope-bounded by Langfuse** so that **any attempt to modify a file not explicitly approved in the runbook is blocked before it touches disk**.

## Acceptance Criteria

- [ ] **AC-1**: Every `apply_chunk()` call in `orchestrator.py` emits a Langfuse trace span linking the step to the originating story ID and runbook path.
- [ ] **AC-2**: A "Scope Bounding" guard is implemented: before applying a block, the target file path is checked against the runbook's declared `[MODIFY]`, `[NEW]`, and `[DELETE]` paths. If the file is not in the approved list and the step is not annotated `cross_cutting: true`, the block is rejected with a structured log event.
- [ ] **AC-3**: Implementation traces are scored in Langfuse for "hallucination rate" — the ratio of rejected blocks (schema validation failures from INFRA-134) to total blocks.
- [ ] **AC-4**: The `cross_cutting: true` annotation in runbook steps relaxes scope constraints for documented exceptions (e.g. shared utility updates).
- [ ] **AC-5**: A `scope_violation` structured log event is emitted for every blocked file, including the file path, step index, and the approved file list.
- [ ] **Negative Test**: An AI-generated implementation step that attempts to modify a file not in the runbook is blocked and does not reach disk.

## Non-Functional Requirements

- Performance: Scope check adds negligible overhead (set membership, < 1ms per block).
- Security: No sensitive file content in Langfuse traces — only paths and metadata.
- Compliance: SOC2 — all scope violations are audit-logged.
- Observability: Langfuse trace scoring for hallucination rate; structured `scope_violation` log events.

## Linked ADRs

- ADR-005 (AI-Driven Governance Preflight)
- ADR-012 (Retry and Backoff Utilities)

## Linked Journeys

- JRN-065

## Impact Analysis Summary

Components touched: `orchestrator.py`, `implement.py`, `telemetry.py`, `parser.py` (extract approved file list)
Workflows affected: `/implement`
Risks identified: Scope-bounding may block legitimate cross-cutting changes — mitigated by `cross_cutting: true` annotation.

## Test Strategy

- Unit test: mock `apply_chunk()` with a file not in the approved list; assert block is rejected and `scope_violation` is logged.
- Unit test: mock `apply_chunk()` with `cross_cutting: true`; assert file is allowed.
- Integration test: run `agent implement` on a real runbook; verify Langfuse traces are emitted with correct story ID linkage.

## Rollback Plan

Disable the scope-bounding guard by setting a feature flag or removing the check in `orchestrator.py`. Langfuse tracing can remain as passive instrumentation.

## Copyright

Copyright 2026 Justin Cook
