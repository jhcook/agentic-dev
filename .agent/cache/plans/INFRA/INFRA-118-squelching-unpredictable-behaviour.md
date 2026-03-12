# INFRA-118: Squelching Unpredictable Behaviour

## State
IN_PROGRESS

## Related Story
INFRA-119, INFRA-120, INFRA-121, INFRA-122

## Summary
This plan outlines the implementation of a deterministic governance layer surrounding Large Language Model (LLM) interactions. By implementing a middleware-based architecture, we will enforce strict schema validation on inputs/outputs, inject runtime guardrails to prevent recursive loops, and integrate comprehensive OpenTelemetry tracing to provide visibility into non-deterministic failure modes.

## Objectives
- Standardize LLM I/O using strict schema enforcement (Pydantic/JSON Schema) to eliminate parsing errors.
- Implement a "Circuit Breaker" and "Turn Limit" logic to prevent infinite LLM-to-LLM or Agent-to-Tool loops.
- Establish a high-fidelity observability pipeline that captures prompt templates, raw completions, and token usage via distributed tracing.

## Milestones
- **M1: Strict I/O Validation Layer (INFRA-119)**
  - Implement a validation decorator/middleware for all LLM service calls.
  - Integrate Pydantic V2 for high-performance response parsing and auto-retries on schema mismatch.
  - Sanitize input prompts to prevent injection and ensure structural integrity.
- **M2: Loop Guardrails & State Control (INFRA-120)**
  - Develop a "Turn Controller" context manager that tracks iterations per request ID.
  - Implement hard limits on maximum token consumption per session.
  - Define state-machine constraints to ensure agents cannot transition between invalid operational states.
- **M3: Observability & Tracing Integration (INFRA-121)**
  - Integrate OpenTelemetry (OTel) instrumentation for LLM providers (OpenAI/Anthropic/Local).
  - Configure Span attributes to include `model_name`, `temperature`, `top_p`, and `latency_ms`.
  - Integrate Langfuse as the primary LLMOps backend to interpret OTel traces and visualize "Agent Chains" and complex tool-loop executions.
  - Implement programmatic trace scoring in Langfuse to track "Hallucination Rates" based on schema validation failures from M1.

## Risks & Mitigations
- **Risk: Increased Latency**
  - *Mitigation:* Use compiled validation logic (Pydantic V2) and ensure tracing exports are handled asynchronously in a background thread.
- **Risk: Blocking Legitimate Complex Reasoning**
  - *Mitigation:* Implement dynamic guardrail thresholds that can be tuned per-model or per-use-case via feature flags.
- **Risk: Exposure of Sensitive Data in Logs**
  - *Mitigation:* Implement a PII-scrubbing middleware within the OTel processor to mask sensitive strings before export.

## Verification
- **Schema Compliance:** Unit tests using synthetic "malformed" LLM responses must trigger `ValidationError` and subsequent graceful handling.
- **Loop Prevention:** An integration test simulating an agent "hallucinating" a recursive tool call must be forcefully terminated at exactly $N$ turns.
- **Trace Consistency:** Confirm that 100% of LLM calls generate a trace ID that links the originating user request to the final generated output.

## Copyright

Copyright 2026 Justin Cook
