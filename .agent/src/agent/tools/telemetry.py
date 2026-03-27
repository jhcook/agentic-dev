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

"""telemetry module."""

import time
import functools
from typing import Any, Callable, Dict, List, Optional
from opentelemetry import trace
from agent.core.logger import get_logger

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

# In-memory metrics buffer for CLI reporting
_METRICS_REGISTRY: Dict[str, List[Dict[str, Any]]] = {}

def track_tool_usage(tool_domain: str):
    """
    Decorator to instrument tools with structured logging and performance metrics.
    
    Args:
        tool_domain: The domain category (e.g., 'project', 'knowledge')
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tool_name = f"{tool_domain}.{func.__name__}"
            span_name = f"tool_call:{tool_name}"
            
            start_time = time.perf_counter()
            status = "success"
            result_count = 0
            hit = True

            with tracer.start_as_current_span(span_name) as span:
                span.set_attribute("tool.name", tool_name)
                span.set_attribute("tool.domain", tool_domain)
                
                try:
                    result = func(*args, **kwargs)
                    
                    # Interpret result for metrics
                    if result is None or (isinstance(result, str) and "not found" in result.lower()):
                        hit = False
                        status = "miss"
                    elif isinstance(result, list):
                        result_count = len(result)
                    
                    return result
                except Exception as e:
                    status = "error"
                    span.record_exception(e)
                    logger.error(f"Tool {tool_name} failed", extra={"error": str(e)})
                    raise
                finally:
                    latency = (time.perf_counter() - start_time) * 1000
                    span.set_attribute("tool.latency_ms", latency)
                    span.set_attribute("tool.status", status)
                    
                    metric_entry = {
                        "timestamp": time.time(),
                        "latency_ms": latency,
                        "status": status,
                        "result_count": result_count,
                        "hit": hit
                    }
                    
                    if tool_name not in _METRICS_REGISTRY:
                        _METRICS_REGISTRY[tool_name] = []
                    _METRICS_REGISTRY[tool_name].append(metric_entry)
                    
                    logger.info(
                        f"Tool executed: {tool_name}",
                        extra={
                            "tool": tool_name,
                            "latency_ms": round(latency, 2),
                            "status": status,
                            "hit": hit,
                            "result_count": result_count
                        }
                    )
        return wrapper
    return decorator

def get_tool_metrics(tool_name: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve summarized metrics from the registry."""
    if tool_name:
        return {tool_name: _METRICS_REGISTRY.get(tool_name, [])}
    return _METRICS_REGISTRY
