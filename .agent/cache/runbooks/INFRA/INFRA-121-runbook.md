# STORY-ID: INFRA-121: Squelching Unpredictable Behaviour (Observability)

## State

COMMITTED

## Goal Description

The goal of this story is to implement comprehensive OpenTelemetry (OTel) instrumentation for LLM workflows, specifically targeting Langfuse as the backend collector. This is critical for moving beyond basic logging into distributed tracing of non-deterministic "Agent Chains". By capturing prompt templates, tool interactions, and performance metrics (latency), we enable SREs to perform root-cause analysis on hallucinations and bottlenecks. The implementation will ensure that validation failures are automatically reflected in trace scores and that all telemetry respects PII scrubbing requirements to maintain compliance.

## Linked Journeys

- JRN-102: Investigating Production Hallucinations
- JRN-105: Monitoring LLM Provider Latency

## Panel Review Findings

### @Architect
- **ADR Compliance**: This implementation directly fulfills ADR-042. Using standard OTel exporters ensures we are not locked into a single vendor, while Langfuse provides the specific LLM-centric visualization needed.
- **Boundaries**: All telemetry logic should be encapsulated in `agent.core.telemetry` to avoid polluting core business logic with instrumentation boilerplate.

### @Qa
- **Reliability**: The requirement for "graceful handling of backend unavailability" is key. We must ensure that OTel is initialized in a non-blocking way, using the `BatchSpanProcessor`.
- **Latency**: We need to verify the `latency_ms` calculation uses `time.perf_counter()` for high-precision measurement.

### @Security
- **PII Scrubbing**: The prompt and completion attributes are high-risk for PII leakage. We must explicitly call `scrub_sensitive_data` on all LLM inputs and outputs before they are added as span attributes.
- **Secrets**: Ensure `LANGFUSE_SECRET_KEY` is handled via the existing `SecretManager` and not logged or exposed in traces.

### @Product
- **Value**: Visualizing nested tool loops is the highest value item here. It allows us to see exactly where an agent might be getting stuck in a cycle.
- **Acceptance Criteria**: The `score=0` metric for validation failures is a great way to trigger automated alerts for low-quality model outputs.

### @Observability
- **Semantic Conventions**: We should use the OpenInference semantic conventions (e.g., `llm.request.model`, `llm.usage.total_tokens`) to ensure compatibility with modern LLMOps dashboards.
- **Performance**: Instrumentation overhead must be minimal. Batching spans is mandatory.

### @Docs
- **Sync**: The `docs/observability.md` (or equivalent) needs to be updated to show developers how to view their traces in Langfuse and how to add custom spans for new tools.

### @Compliance
- **Data Privacy**: Ensure that the OTel collector configuration aligns with our SOC2 requirements for data retention of model inputs. Trace data should follow the same TTL as standard logs.

### @Backend
- **Implementation**: We should use decorators or context managers to simplify the instrumentation of the `AIService` and `Orchestrator`.

## Codebase Introspection

### Targeted File Contents (from source)

(No targeted files identified in story. All implementation will be via new utility modules to satisfy the requirement for machine-executable logic without pre-existing source for specific core files.)

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| `.agent/tests/core/test_telemetry.py` | N/A | New File | Create comprehensive unit tests for telemetry |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| `ENABLE_OTEL_TRACING` | Story Requirement | `false` (Default) | Yes |
| Overhead Limit | Non-Functional Req | <10ms | Yes |

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Consolidation of latency measurement across the LLM Gateway.
- [ ] Standardization of `scrub_sensitive_data` usage in logging vs. tracing.

## Implementation Steps

### Step 0.5: Add Dependencies

Add the required OpenTelemetry trace exporter dependency.

#### [MODIFY] .agent/pyproject.toml

```toml
<<<SEARCH
    "opentelemetry-api~=1.38.0",
    "opentelemetry-sdk~=1.38.0",
    "ruff>=0.1.0",
===
    "opentelemetry-api~=1.38.0",
    "opentelemetry-sdk~=1.38.0",
    "opentelemetry-exporter-otlp~=1.38.0",
    "ruff>=0.1.0",
>>>
```

### Step 1: Create Telemetry Core Module

This module initializes the OpenTelemetry tracer, configures the Langfuse OTLP exporter, and provides the primary instrumentation interface for the application.

#### [NEW] .agent/src/agent/core/telemetry.py

```python
"""
OpenTelemetry instrumentation core for LLM tracing and Langfuse integration.

This module provides the necessary setup for tracing LLM requests, tool calls,
and performance metrics using standard OpenInference semantic conventions.
"""

import os
import time
import functools
import logging
from typing import Any, Dict, Optional, Callable
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

from agent.core.security import scrub_sensitive_data
from agent.core.logger import get_logger

logger = get_logger(__name__)

# Constants for OpenInference attributes
ATTR_LLM_MODEL = "llm.request.model"
ATTR_LLM_PROMPT = "llm.request.prompt"
ATTR_LLM_COMPLETION = "llm.response.completion"
ATTR_LATENCY_MS = "latency_ms"
ATTR_SCORE = "score"

_TRACER_NAME = "agentic-infra"
_INITIALIZED = False

def initialize_telemetry() -> None:
    """
    Initialize the OpenTelemetry TracerProvider and OTLP Exporter.

    Configures the exporter to point to Langfuse or a generic OTLP collector.
    Fails gracefully if configuration is missing.
    """
    global _INITIALIZED
    if _INITIALIZED:
        return

    enabled = os.getenv("ENABLE_OTEL_TRACING", "false").lower() == "true"
    if not enabled:
        logger.info("OpenTelemetry tracing is disabled via ENABLE_OTEL_TRACING.")
        return

    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not otlp_endpoint:
        logger.warning("OTEL_EXPORTER_OTLP_ENDPOINT not set. Tracing will be inactive.")
        return

    resource = Resource.create({"service.name": "agentic-service"})
    provider = TracerProvider(resource=resource)
    
    # Langfuse expects OTLP traces. Headers should be set via environment variables.
    # OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic <base64>"
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    
    trace.set_tracer_provider(provider)
    _INITIALIZED = True
    logger.info("OpenTelemetry telemetry initialized successfully.")

def get_tracer() -> trace.Tracer:
    """
    Get the application tracer instance.

    Returns:
        The OpenTelemetry tracer.
    """
    return trace.get_tracer(_TRACER_NAME)

def trace_llm_call(model_name: str):
    """
    Decorator for instrumenting LLM gateway calls.

    Args:
        model_name: The name/version of the model being called.
    """
    def decorator(func: Callable):
        """The actual decorator."""
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            """The wrapped function."""
            tracer = get_tracer()
            with tracer.start_as_current_span("llm_request") as span:
                start_time = time.perf_counter()
                
                # Capture prompt if available in kwargs
                prompt = kwargs.get("prompt") or (args[0] if args else "unknown")
                scrubbed_prompt = scrub_sensitive_data(str(prompt))
                
                span.set_attribute(ATTR_LLM_MODEL, model_name)
                span.set_attribute(ATTR_LLM_PROMPT, scrubbed_prompt)
                
                try:
                    result = await func(*args, **kwargs)
                    
                    # Capture completion
                    scrubbed_completion = scrub_sensitive_data(str(result))
                    span.set_attribute(ATTR_LLM_COMPLETION, scrubbed_completion)
                    
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.status.Status(trace.status.StatusCode.ERROR))
                    raise
                finally:
                    latency = (time.perf_counter() - start_time) * 1000
                    span.set_attribute(ATTR_LATENCY_MS, latency)
        return wrapper
    return decorator

def record_validation_failure(span: Optional[trace.Span] = None) -> None:
    """
    Attach a failure score to the current span or a provided span.

    Args:
        span: Optional span to attach the score to.
    """
    target_span = span or trace.get_current_span()
    if target_span:
        target_span.set_attribute(ATTR_SCORE, 0)
        target_span.add_event("validation_failed")
```

### Step 2: Create LLM Tracing Wrapper

This module provides a specialized context manager for more granular control over LLM tool-loops, satisfying Scenario 1 and 3 of the AC.

#### [NEW] .agent/src/agent/core/ai/tracing.py

```python
# Copyright 2026 Justin Cook
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Specialized tracing utilities for LLM provider interactions and tool loops.
"""

import time
from contextlib import contextmanager
from typing import Generator, Optional
from opentelemetry import trace
from agent.core.telemetry import (
    get_tracer, 
    ATTR_LLM_MODEL, 
    ATTR_LLM_PROMPT, 
    ATTR_LLM_COMPLETION, 
    ATTR_LATENCY_MS,
    ATTR_SCORE,
    scrub_sensitive_data
)

@contextmanager
def llm_span(
    name: str, 
    model: str, 
    prompt: str
) -> Generator[trace.Span, None, None]:
    """
    Context manager for manual LLM span control.

    Args:
        name: Name of the span (e.g., 'agent_reasoning').
        model: Model version string.
        prompt: Raw prompt text (will be scrubbed).
    """
    tracer = get_tracer()
    start_time = time.perf_counter()
    
    scrubbed_prompt = scrub_sensitive_data(prompt)
    
    with tracer.start_as_current_span(name) as span:
        span.set_attribute(ATTR_LLM_MODEL, model)
        span.set_attribute(ATTR_LLM_PROMPT, scrubbed_prompt)
        
        try:
            yield span
        finally:
            latency = (time.perf_counter() - start_time) * 1000
            span.set_attribute(ATTR_LATENCY_MS, latency)

def mark_as_hallucination(span: Optional[trace.Span] = None) -> None:
    """
    Specific helper for marking a trace as a hallucination (score=0).

    Args:
        span: The span to mark.
    """
    target_span = span or trace.get_current_span()
    if target_span:
        target_span.set_attribute(ATTR_SCORE, 0)
        target_span.set_attribute("llm.failure_type", "hallucination")
```

### Step 3: Define Telemetry Tests

Verify that PII scrubbing and latency calculations are correct.

#### [NEW] .agent/tests/core/test_telemetry.py

```python
# Copyright 2026 Justin Cook
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Unit tests for the telemetry instrumentation logic.
"""

import pytest
from unittest.mock import MagicMock, patch
from agent.core.telemetry import trace_llm_call, ATTR_LLM_PROMPT, ATTR_LATENCY_MS

@pytest.mark.asyncio
async def test_trace_llm_call_scrubs_pii():
    """
    Ensure that the trace_llm_call decorator scrubs PII from attributes.
    """
    # Mocking scrub_sensitive_data to verify it's called
    with patch("agent.core.telemetry.scrub_sensitive_data") as mock_scrub:
        mock_scrub.return_value = "REDACTED"
        
        @trace_llm_call(model_name="gpt-4o")
        async def mock_llm(prompt: str):
            """Mock llm call."""
            return "Result"

        # Mock trace span
        with patch("agent.core.telemetry.get_tracer") as mock_tracer:
            mock_span = MagicMock()
            mock_tracer.return_value.start_as_current_span.return_value.__enter__.return_value = mock_span
            
            await mock_llm(prompt="My email is test@example.com")
            
            # Verify scrub was called
            mock_scrub.assert_called()
            # Verify span attribute was set to redacted value
            mock_span.set_attribute.assert_any_call(ATTR_LLM_PROMPT, "REDACTED")

@pytest.mark.asyncio
async def test_trace_llm_call_records_latency():
    """
    Ensure that latency_ms is recorded as a float.
    """
    @trace_llm_call(model_name="gpt-4o")
    async def mock_llm(prompt: str):
        """Mock llm call."""
        return "Result"

    with patch("agent.core.telemetry.get_tracer") as mock_tracer:
        mock_span = MagicMock()
        mock_tracer.return_value.start_as_current_span.return_value.__enter__.return_value = mock_span
        
        await mock_llm(prompt="hello")
        
        # Check if set_attribute was called with latency_ms
        calls = [call.args for call in mock_span.set_attribute.call_args_list]
        latency_call = [c for c in calls if c[0] == ATTR_LATENCY_MS]
        assert len(latency_call) == 1
        assert isinstance(latency_call[0][1], float)
```

## Verification Plan

### Automated Tests
- [ ] Run `pytest .agent/tests/core/test_telemetry.py` to verify scrubbing and latency logic.
- [ ] Run `agent audit --story INFRA-121` to ensure compliance gates are satisfied.

### Manual Verification
- [ ] Set `ENABLE_OTEL_TRACING=true` and `OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318/v1/traces"`.
- [ ] Run a test LLM query via `agent query "What is the system health?"`.
- [ ] Observe trace arrival in a local OTLP collector (or Langfuse if configured) and check for:
  - Presence of `latency_ms` attribute.
  - Redaction of email addresses or keys in the `llm.request.prompt` attribute.
  - Correct nesting of spans for tool-calling loops.

## Definition of Done

### Documentation
- [ ] CHANGELOG.md updated with "Added OpenTelemetry instrumentation for LLM workflows with Langfuse support".
- [ ] Added internal README note on enabling tracing via `ENABLE_OTEL_TRACING`.

### Observability
- [ ] Logs are structured and free of PII.
- [ ] New structured `extra=` dicts added to LLM gateway logging for trace correlation.

### Testing
- [ ] All existing tests pass.
- [ ] New tests added for the `telemetry.py` and `tracing.py` modules.

## Copyright

Copyright 2026 Justin Cook
