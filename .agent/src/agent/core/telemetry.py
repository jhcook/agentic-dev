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