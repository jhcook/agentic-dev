# INFRA-121: Squelching Unpredictable Behaviour (Observability)

## State

REVIEW_NEEDED

## Problem Statement

Standard application logs provide insufficient visibility into the non-deterministic nature of LLM workflows. Without granular tracing of prompt templates, tool interactions, and execution latency, SREs cannot effectively root-cause failures, hallucinations, or performance bottlenecks in production. Generic APMs (like Datadog/Grafana) struggle to properly visualize nested "Agent Chains".

## User Story

As an **SRE**, I want **OpenTelemetry (OTel) traces covering prompt templates, tool input/output, and latency exported specifically to Langfuse** so that **we can visualize complex agent tool-loops, debug non-deterministic failures, and programmatically score trace runs based on validation failures.**

## Acceptance Criteria

- [ ] **Scenario 1**: Given an LLM request execution, When the workflow is triggered, Then an OpenTelemetry span is generated containing the prompt template name, model version, and tool input/output data.
- [ ] **Scenario 2**: All LLM spans must include a `latency_ms` attribute and be successfully exported to the Langfuse collector endpoint, rendering correctly as a linked trace.
- [ ] **Scenario 3**: Ensure that validation failures automatically attach a `score=0` (Validation Failed) metric to the corresponding Langfuse trace.
- [ ] **Negative Test**: System handles LLMOps backend unavailability gracefully by dropping spans without blocking the primary LLM inference execution or increasing user-facing latency.

## Non-Functional Requirements

- **Performance**: Telemetry instrumentation must introduce <10ms of overhead per request.
- **Security**: Sensitive user data or PII must be scrubbed from prompt/response attributes before export.
- **Compliance**: Trace data retention must align with corporate data privacy policies for model inputs.
- **Observability**: Spans must use standard semantic conventions for LLM instrumentation (e.g., OpenInference or OTel experimental attributes).

## Linked Plan

- INFRA-118: Squelching Unpredictable Behaviour

## Linked ADRs

- ADR-042: Adoption of OpenTelemetry for Distributed LLM Tracing

## Linked Journeys

- JRN-102: Investigating Production Hallucinations
- JRN-105: Monitoring LLM Provider Latency

## Impact Analysis Summary

**Components touched:**
- LLM Gateway Service
- Tool Orchestration Layer
- OpenTelemetry Collector Configuration
- `agent.core.logger` (Application-wide log format updated to include `trace_id` and `span_id`)

**Workflows affected:**
- Inference request pipeline
- Tool calling and response parsing

**Risks identified:**
- Potential for PII leakage in trace spans.
- Increased memory footprint of the collector under high throughput.

## Test Strategy

- **Integration Testing**: Verify span arrival in the LLMOps backend using a staging environment.
- **Load Testing**: Measure CPU and latency impact with and without tracing enabled.
- **Unit Testing**: Validate that the PII scrubbing logic correctly redacts defined patterns.

## Rollback Plan

- Disable tracing via environment variable `ENABLE_OTEL_TRACING=false`.
- If performance degrades, revert the OTel SDK integration via a hotfix and redeploy.

## Copyright

Copyright 2026 Justin Cook
