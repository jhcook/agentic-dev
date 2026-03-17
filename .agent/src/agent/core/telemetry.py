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
OpenTelemetry instrumentation core for LLM tracing and Langfuse integration.

This module provides the necessary setup for tracing LLM requests, tool calls,
and performance metrics using standard OpenInference semantic conventions.
"""

import os
import time
import functools
import logging
from typing import Any, Dict, Optional, Callable, TypeVar, Coroutine, ParamSpec
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, ReadableSpan
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
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

# Attribute keys that should always be scrubbed
_PII_SENSITIVE_KEYS = frozenset({
    ATTR_LLM_PROMPT,
    ATTR_LLM_COMPLETION,
})

# Substrings — any attribute key containing these is also scrubbed
_PII_SENSITIVE_SUBSTRINGS = ("prompt", "completion", "input", "output")

_TRACER_NAME = "agentic-infra"
_INITIALIZED = False


class PiiScrubbingSpanProcessor:
    """
    SpanProcessor that scrubs PII from span attributes before export.

    Ensures that all exported spans have sensitive attributes
    (prompts, completions, inputs, outputs) run through
    ``scrub_sensitive_data`` regardless of whether the calling code
    remembered to scrub manually.
    """

    def __init__(self, next_processor: BatchSpanProcessor) -> None:
        """Wrap an existing processor, scrubbing spans before forwarding."""
        self._next = next_processor

    def on_start(self, span: ReadableSpan, parent_context: object = None) -> None:
        """Forward span start to the next processor."""
        self._next.on_start(span, parent_context)

    def on_end(self, span: ReadableSpan) -> None:
        """Scrub PII-sensitive attributes then forward to the next processor."""
        if span.attributes:
            for key, value in list(span.attributes.items()):
                if isinstance(value, str) and self._is_sensitive(key):
                    # Mutate in-place where possible; for immutable mappings
                    # fall back to patching the internal dict.
                    try:
                        span.attributes[key] = scrub_sensitive_data(value)
                    except TypeError:
                        # ReadableSpan uses a MappingProxyType — patch internals
                        attrs = dict(span.attributes)
                        attrs[key] = scrub_sensitive_data(value)
                        object.__setattr__(span, "_attributes", attrs)
        self._next.on_end(span)

    def shutdown(self) -> None:
        """Shutdown the wrapped processor."""
        self._next.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Flush the wrapped processor."""
        return self._next.force_flush(timeout_millis)

    @staticmethod
    def _is_sensitive(key: str) -> bool:
        """Return True if the attribute key should be scrubbed."""
        if key in _PII_SENSITIVE_KEYS:
            return True
        key_lower = key.lower()
        return any(sub in key_lower for sub in _PII_SENSITIVE_SUBSTRINGS)


def initialize_telemetry() -> None:
    """
    Initialize the OpenTelemetry TracerProvider and OTLP Exporter.

    Configures the exporter to point to Langfuse or a generic OTLP collector.
    Wraps the exporter with a ``PiiScrubbingSpanProcessor`` to ensure all
    exported spans have sensitive attributes scrubbed.
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
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter  # ADR-025: lazy import
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
    batch_processor = BatchSpanProcessor(exporter)

    # Wrap with PII scrubbing so every exported span is clean
    pii_processor = PiiScrubbingSpanProcessor(batch_processor)
    provider.add_span_processor(pii_processor)

    trace.set_tracer_provider(provider)
    _INITIALIZED = True
    logger.info("OpenTelemetry telemetry initialized with PII scrubbing.")

def get_tracer() -> trace.Tracer:
    """
    Get the application tracer instance.

    Returns:
        The OpenTelemetry tracer.
    """
    return trace.get_tracer(_TRACER_NAME)

def is_tracing_enabled() -> bool:
    """Return whether OpenTelemetry tracing has been initialised."""
    return _INITIALIZED

P = ParamSpec('P')
R = TypeVar('R')

def trace_llm_call(model_name: str):
    """
    Decorator for instrumenting LLM gateway calls.

    Args:
        model_name: The name/version of the model being called.
    """
    def decorator(func: Callable[P, Coroutine[Any, Any, R]]) -> Callable[P, Coroutine[Any, Any, R]]:
        """The actual decorator."""
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
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