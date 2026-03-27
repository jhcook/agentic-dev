# ADR-046: Audit and Observability Framework

## Context
As the agentic system expands with new tool domains (web, testing, dependencies, context), executing operations blindly via bare Python function calls creates significant blind spots for debugging and security audits. A unified framework is needed to securely log tool execution metadata, arguments, outputs, and integrate with OpenTelemetry. 

## Decision
We implemented a centralized Audit and Observability Framework via `.agent/src/agent/core/governance/audit_handler.py`. 

1. **Decorator & Context Manager Approach**: We use an `@audit_tool(domain, action)` decorator to seamlessly wrap any public tool function without requiring verbose boilerplate inside the core implementation logic. The context manager `AuditContext` records start times, duration, and captures unhandled exceptions effortlessly.
2. **OpenTelemetry Integration**: Each wrapped execution natively creates a new OpenTelemetry child span containing exactly the tool execution context via `tracer.start_as_current_span(f"{domain}.{action}")`.
3. **Strict Validation & PII Redaction**: All logged execution metadata (args, kwargs) is mandatorily passed through `scrub_sensitive_data` to ensure zero PII leakage into log systems, enforcing SOC2 compliance automatically.
4. **Structured Logging Consistency**: All execution results and failures produce standardized `AUDIT_RECORD` logs.

## Consequences
- **Positive**: Complete systemic observability without complex manual spans. Complete PII protection for downstream tracing backends.
- **Negative**: Adds a minor latency overhead when invoking tools due to telemetry and regex-based PII scrubbing operations. All public functions exposed to LLM MUST remember to use the `@audit_tool` decorator.

## Copyright

Copyright 2026 Justin Cook

