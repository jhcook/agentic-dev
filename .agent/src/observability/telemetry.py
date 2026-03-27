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
OpenTelemetry integration for command tracing and custom metric exports.
"""

import os
from typing import Optional
from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

def setup_telemetry(service_name: str = "agent-cli") -> None:
    """Initialize OpenTelemetry providers for tracing and metrics.

    When ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set, spans and metrics are
    exported via OTLP/gRPC.  When it is absent, providers are registered
    but no exporter is attached (no-op) — console output is intentionally
    suppressed to keep CLI output clean.
    """
    resource = Resource.create({"service.name": service_name})

    # 1. Tracing Infrastructure
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    tracer_provider = TracerProvider(resource=resource)

    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            span_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
        except ImportError:
            pass  # OTLP package not installed — remain no-op

    trace.set_tracer_provider(tracer_provider)

    # 2. Metrics Infrastructure
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
            metric_exporter = OTLPMetricExporter(endpoint=otlp_endpoint)
            reader = PeriodicExportingMetricReader(metric_exporter)
            meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
        except ImportError:
            meter_provider = MeterProvider(resource=resource)
    else:
        # No endpoint — register provider with no readers (no-op, no console noise)
        meter_provider = MeterProvider(resource=resource)

    metrics.set_meter_provider(meter_provider)

def get_tracer(name: str = "agent.engine") -> trace.Tracer:
    """Return a tracer instance for the specified namespace."""
    return trace.get_tracer(name)

def get_meter(name: str = "agent.metrics") -> metrics.Meter:
    """Return a meter instance for recording custom metrics."""
    return metrics.get_meter(name)

# Pre-defined metrics for common tasks
meter = get_meter()
token_counter = meter.create_counter(
    name="llm.tokens.consumed",
    description="Total number of LLM tokens consumed",
    unit="1"
)

task_failure_counter = meter.create_counter(
    name="task.failures",
    description="Number of parallel task execution failures",
    unit="1"
)

def record_token_usage(model: str, input_tokens: int, output_tokens: int) -> None:
    """Record token usage metrics with model and type attributes."""
    token_counter.add(input_tokens, {"model": model, "type": "input"})
    token_counter.add(output_tokens, {"model": model, "type": "output"})

def record_task_error(task_id: str, error_type: str) -> None:
    """Record a task failure event for negative scenario reporting."""
    task_failure_counter.add(1, {"task_id": task_id, "error": error_type})
