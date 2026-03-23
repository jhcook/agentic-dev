# INFRA-169: Implement Phased Generation Orchestrator with Concurrency and Retries

## State

COMMITTED

## Problem Statement

Large-scale generation tasks are currently processed serially, leading to significant latency bottlenecks. Additionally, the lack of granular retry logic means that a single transient failure within a multi-phase generation job causes the entire process to fail, resulting in wasted compute and poor reliability.

## User Story

As a **Backend Engineer**, I want **the orchestrator to execute generation phases concurrently with per-chunk retry logic** so that **system throughput is optimized and long-running tasks are resilient to intermittent failures.**

## Acceptance Criteria

- [ ] **Scenario 1**: Given a generation task with multiple independent chunks in a single phase, When the orchestrator is triggered, Then it must process those chunks in parallel using async/await patterns.
- [ ] **Scenario 2**: If a specific chunk fails due to a transient error, the orchestrator must execute a retry (with exponential backoff) specifically for that chunk without restarting the entire phase.
- [ ] **Negative Test**: System handles a "Max Retries Exceeded" event gracefully by marking the specific chunk as failed and preventing downstream phases from starting, while preserving the state of successful chunks.
- [ ] **Idempotency — implement**: Running `agent implement` a second time must skip already-applied S/R blocks (REPLACE text present) and identical [NEW] files, producing no changes.
- [ ] **Idempotency — new-runbook**: Running `agent new-runbook` when a valid runbook exists must validate it and exit cleanly. Use `--force` to regenerate.
- [ ] **[NEW] file guard**: Runbook generation must refuse to mark existing on-disk files as `[NEW]`. Files that exist must use `[MODIFY]` with S/R blocks.

## Non-Functional Requirements

- **Performance**: Async orchestration should demonstrate a measurable reduction in total task duration compared to serial execution.
- **Security**: Retry logic must not expose internal API keys or sensitive metadata in logs.
- **Compliance**: N/A.
- **Observability**: Emit telemetry for chunk-level success/failure rates and retry counts to the centralized monitoring dashboard.

## Linked ADRs

- ADR-015: Phased Generation Architecture

## Linked Journeys

- JRN-022: High-Volume Content Generation

## Impact Analysis Summary

- **Components touched**:
  - `.agent/src/agent/core/implement/orchestrator.py` — phased orchestration, concurrency, telemetry callbacks
  - `.agent/src/agent/core/implement/retry.py` — `retry_with_backoff` with `on_retry`/`on_failure` callbacks, `MaxRetriesExceededError`
  - `.agent/src/agent/core/implement/telemetry_helper.py` — `emit_chunk_event` for structured chunk lifecycle logging
  - `.agent/src/agent/core/implement/guards.py` — idempotency checks for S/R and `[NEW]` file blocks
  - `.agent/src/agent/core/implement/security.py` — `OrchestrationSecurityFilter`, `sanitize_error_message`
  - `.agent/src/agent/core/implement/sr_validation.py` — S/R block validation and re-anchoring
  - `.agent/src/agent/commands/implement.py` — `asyncio.run()` wiring, `use_concurrency` parallel branch
  - `.agent/src/agent/commands/runbook.py` — `--force` flag, existing runbook validation
  - `.agent/src/agent/commands/runbook_generation.py` — `[NEW]` file guard for existing files
  - `.agent/src/agent/core/config.py` — `ENABLE_CONCURRENT_ORCHESTRATION` feature flag
  - `.agent/src/agent/core/ai/prompts.py` — prompt engineering for chunk generation
  - `.agent/docs/backend/orchestration-concurrency.md` — concurrency design documentation
  - `.agent/docs/backend/retry-and-error-states.md` — retry/error state documentation
  - `.agent/src/agent/core/implement/tests/` — new tests for orchestrator, retry, telemetry, security
  - `.agent/src/agent/core/tests/__init__.py` — package init to resolve test name collisions
  - `.agent/src/agent/core/implement/tests/__init__.py` — package init for test discovery
  - `.agent/rules/400-lean-code.mdc` — updated cognitive complexity thresholds (cross-ref: INFRA-170)

## Test Strategy

- **Unit Testing**: Validate the core loop logic in `orchestrator.py` using mocked dependencies.
- **Integration Testing**: Simulate transient network failures to verify that retry logic triggers and succeeds.
- **Concurrency Testing**: Execute batch jobs with high chunk counts to ensure `asyncio` loop stability and correct phase sequencing.
- **Idempotency Testing**: Verify S/R blocks skip when REPLACE content already present; verify `[NEW]` file blocks skip when content identical.
- **File Guard Testing**: Verify `[NEW]` file guard errors when targeting pre-existing files during runbook generation.
- **Security Testing**: Verify `OrchestrationSecurityFilter` scrubs API keys from log output; verify `sanitize_error_message` redacts sensitive data.
- **Telemetry Testing**: Verify `emit_chunk_event` produces structured log entries for chunk_start, chunk_success, chunk_retry, chunk_failure lifecycle events.

## Rollback Plan

- Revert `orchestrator.py` to the previous version (tagged in INFRA-166).
- If deployed via feature flag, toggle `ENABLE_CONCURRENT_ORCHESTRATION` to `FALSE`.

## Copyright

Copyright 2026 Justin Cook