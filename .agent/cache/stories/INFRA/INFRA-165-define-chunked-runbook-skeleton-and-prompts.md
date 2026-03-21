# INFRA-165: Define Chunked Runbook Skeleton and Prompts

## State

COMMITTED

## Problem Statement

Generating comprehensive, long-form runbooks in a single LLM request often leads to context loss, hallucinations, or truncated output due to token limits. We need a modular approach that first defines a high-level structure and then populates specific content blocks to ensure depth, accuracy, and logical consistency.

## User Story

As a **DevOps Engineer**, I want a **multi-phase generation pipeline (Skeleton and Block generation)** so that **I can produce high-quality, detailed runbooks that exceed standard LLM context windows without losing document coherence.**

## Acceptance Criteria

- [ ] **AC-1**: Given a runbook objective and metadata, When the Phase 1 prompt is executed, Then the system generates a valid JSON Skeleton containing the table of contents and structural headers.
- [ ] **AC-2**: Phase 2 prompts must successfully ingest a specific Skeleton section as context and output a JSON Block containing detailed technical instructions and troubleshooting steps.
- [ ] **AC-3**: System handles malformed LLM output gracefully by validating against the JSON schema and triggering a retry or a specific validation error message.
- [ ] **AC-4**: The context loader must use fuzzy path resolution (via `resolve_path`) so that partial or bare file paths in Impact Analysis are auto-corrected to their real repository location.

## Non-Functional Requirements

- **Performance**: JSON schema validation for generated chunks must complete in under 50ms.
- **Security**: Prompts must include instructions to exclude sensitive credentials or PII placeholder formats.
- **Compliance**: Generation logic must adhere to internal documentation standards (e.g., Markdown formatting).
- **Observability**: Each generation phase must log prompt versioning and token consumption for cost analysis, and MUST use OTel `start_as_current_span` or `tracer.start` for all new flows.

## Linked ADRs

- ADR-014: Modular LLM Prompt Orchestration

## Linked Journeys

- JRN-082: Automated Runbook Generation Workflow

## Impact Analysis Summary

- **Components touched**:
  - `.agent/src/agent/core/implement/chunk_models.py` [NEW]
  - `.agent/src/agent/core/ai/prompts.py`
  - `.agent/src/agent/commands/runbook.py`
  - `.agent/src/agent/core/context.py`
- **Workflows affected**: `agent new-runbook` command execution.
- **Risks identified**: Potential for context drift between independent block generation calls.

## Test Strategy

- **Unit Testing**: Validate Phase 1 and Phase 2 JSON schemas against mock LLM outputs.
- **Integration Testing**: Execute the full two-phase pipeline to ensure the "Skeleton" correctly informs the "Block" generation.
- **Quality Benchmarking**: Use LLM-as-a-judge to score the technical accuracy and formatting of the generated chunks.

## Rollback Plan

- Revert to monolithic prompt templates (Version 0.9) and update the API gateway to point to the legacy generation endpoint.

## Copyright

Copyright 2026 Justin Cook
