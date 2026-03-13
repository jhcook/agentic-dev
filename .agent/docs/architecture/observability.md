# Observability and Tracing

This document outlines the usage of OpenTelemetry to trace and debug LLM flows.

## Enabling Tracing
Tracing is disabled by default. To enable:

```bash
export ENABLE_OTEL_TRACING="true"
export OTEL_EXPORTER_OTLP_ENDPOINT="https://cloud.langfuse.com/api/public/otel/trace"
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic <base64>"
```

## Available Decorators and Context Managers
- `@trace_llm_call(model_name="...")`: A decorator for functions that perform LLM API calls.
- `with llm_span(name, model, prompt) as span:`: A context manager for building spans manually.

Traces automatically scrub sensitive information like email addresses or API keys.
Span properties injected into Python log formatter context automatically `[trace_id=... span_id=...]`.

## Copyright

Copyright 2026 Justin Cook
