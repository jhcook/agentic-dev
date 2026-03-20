# INFRA-164: Chunked Runbook Generation Pipeline

## State

DRAFT

## Problem Statement

The current monolithic generation approach for `agent new-runbook` frequently exceeds LLM context windows, leading to "SEARCH" block hallucinations and total process failures on large stories. Massive retry loops on long-form outputs are costly and unreliable.

## User Story

As a **Developer**, I want the **runbook generation process to be broken into discrete, targeted phases** so that **I can reliably generate complex runbooks without structural errors or context-limit failures.**

## Acceptance Criteria

- [ ] **Scenario 1**: Given a feature story, When the generator starts, Then Phase 1 must produce a structured skeleton (JSON/YAML) listing all required files and high-level operations.
- [ ] **Scenario 2**: For every entry in the skeleton, Phase 2 must trigger independent, parallelizable AI calls that generate implementation blocks using scoped file context.
- [ ] **Scenario 3**: Phase 3 must successfully assemble all generated blocks and the skeleton into a valid, final runbook format.
- [ ] **Negative Test**: System handles a failure in a single implementation block by retrying only that specific chunk rather than restarting the entire pipeline.

## Non-Functional Requirements

- **Performance**: Parallelize Phase 2 calls to minimize total generation latency.
- **Security**: Ensure file context provided to implementation blocks is restricted to the files identified in the skeleton.
- **Compliance**: Maintain a log of tokens consumed per phase for cost auditing.
- **Observability**: Provide a progress bar or status updates identifying the current phase (Skeleton, Block implementation, Assembly).

## Linked ADRs

- ADR-012: Chunked Generation Strategy

## Linked Journeys

- JRN-004: Automated Runbook Creation

## Impact Analysis Summary

- **Components touched**: `RunbookEngine`, `LLMOrchestrator`, `CLI Output Handler`.
- **Workflows affected**: `agent new-runbook` command execution.
- **Risks identified**: Potential increase in total API token overhead; managing state/consistency across three asynchronous phases.

## Test Strategy

- **Unit Testing**: Validate the assembly logic (Phase 3) using mocked skeletons and blocks.
- **Integration Testing**: Verify the hand-off between the skeleton generator and implementation generators.
- **E2E Testing**: Stress test with a 10+ file story to ensure no context window overflows occur.

## Rollback Plan

- Maintain the legacy monolithic generation code path as a feature-flagged fallback (`--legacy-gen`) for one release cycle.

## Copyright

Copyright 2026 Justin Cook