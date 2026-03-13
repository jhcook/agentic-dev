<!--
Copyright 2026 Justin Cook

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

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
