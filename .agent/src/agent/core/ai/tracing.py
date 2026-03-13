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