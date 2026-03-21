# INFRA-166: Implement Phased Generation Orchestrator

## State

DECOMPOSED

## Problem Statement

The current runbook generation process is monolithic and sequential, leading to high latency and a "single point of failure" during long-running LLM calls. If one section fails, the entire process restarts. There is a need for a structured orchestration layer that can parse a runbook skeleton, execute block generation in parallel, and handle transient failures gracefully.

## User Story

As a **DevOps Engineer**, I want **an automated phased generation orchestrator** so that **I can generate complex, high-quality runbooks rapidly and reliably through parallel processing and fault-tolerant retries.**

## Linked Stories

This plan consists of the following child stories:
- INFRA-168: Implement Runbook Skeleton Parser and Assembly Engine
- INFRA-169: Implement Phased Generation Orchestrator with Concurrency and Retries

- **Performance**: Orchestration overhead should add < 500ms to the total generation time; parallel execution should reduce total latency by at least 40% compared to sequential generation.
- **Security**: All parsed skeleton data and generated content must be sanitized to prevent injection attacks.
- **Compliance**: Ensure all generation logs are stored according to corporate data retention policies.
- **Observability**: Implement detailed telemetry for each phase (Parse, Generate, Assemble) and track retry counts per block.

## Linked ADRs

- ADR-012: Implementation of Parallel Processing via Python AsyncIO
- ADR-015: Fault Tolerance and Retry Strategy for LLM Integrations

## Linked Journeys

- JRN-004: Automated Runbook Creation from Incident Metadata

## Impact Analysis Summary

**Components touched**: 
- `orchestrator.py` (Core Logic)
- `parser.py` (Skeleton Logic)
- `assembly_engine.py` (Final Merge)

**Workflows affected**: 
- Runbook Generation Pipeline
- Automated Documentation Updates

**Risks identified**: 
- Potential for rate-limiting on external LLM providers due to increased concurrency.
- Race conditions during the final assembly phase if block indices are not properly tracked.

## Test Strategy

- **Unit Testing**: Validate `orchestrator.py` logic using mocked block generators.
- **Integration Testing**: End-to-end test from skeleton upload to final Markdown output.
- **Load Testing**: Simulate 50+ concurrent block generations to verify parallel efficiency and retry logic stability.

## Rollback Plan

- Revert to `v1.x` sequential generation logic by re-pointing the generation service entry point to the legacy `monolith_generator.py`.
- Feature flag: `ENABLE_PHASED_ORCHESTRATION` can be toggled to `FALSE` in the environment configuration.

## Copyright

Copyright 2026 Justin Cook