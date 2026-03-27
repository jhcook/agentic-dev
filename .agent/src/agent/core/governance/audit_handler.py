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
audit_handler module.

This module provides structured logging decorators and tracking contexts for tool 
operations. It is primarily used to ensure that all automated AI actions (like fetches, 
test runs, codebase modifications) emit standardized AUDIT_RECORD events containing 
action metadata, timing, and outcomes. These records supply the basis for governance 
compliance, strict observability, and platform auditing.
"""


import json
import time
from datetime import datetime
from typing import Any, Dict, Optional, Callable
from functools import wraps
from agent.core.logger import get_logger

_logger = get_logger("agent.audit")

def record_audit_event(
    domain: str, 
    action: str, 
    metadata: Dict[str, Any], 
    status: str = "success"
) -> None:
    """
    Records a structured audit event to the standard log stream.
    
    This utility ensures that critical tool operations are captured in a 
    consistent format suitable for parsing by governance and audit tools.
    
    Args:
        domain: The tool domain (e.g., 'web', 'deps', 'testing', 'context').
        action: The specific operation performed (e.g., 'fetch_url', 'add_dependency').
        metadata: Operation-specific data (e.g., URLs, package names, durations).
        status: The outcome of the operation ('success', 'failure', 'skipped').
    """
    record = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "domain": domain,
        "action": action,
        "status": status,
        "metadata": metadata
    }
    # Structured logging with a prefix to facilitate log filtering
    _logger.info(f"AUDIT_RECORD:{json.dumps(record)}")

class AuditContext:
    """
    Context manager for automated audit logging of tool execution.

    Wraps an operation to track its duration, success/failure status, and metadata.
    """

    def __init__(self, domain: str, action: str, metadata: Dict[str, Any]):
        """
        Initializes the audit context.
        
        Args:
            domain: The tool domain.
            action: The action identifier.
            metadata: Initial metadata for the event.
        """
        self.domain = domain
        self.action = action
        self.metadata = metadata.copy()
        self.start_time: Optional[float] = None

    def __enter__(self):
        """Starts the execution timer."""
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Calculates duration and records the audit event upon exit."""
        if self.start_time is not None:
            duration = time.perf_counter() - self.start_time
            self.metadata["duration_ms"] = int(duration * 1000)
        
        status = "success" if exc_type is None else "failure"
        if exc_val:
            self.metadata["error_type"] = exc_type.__name__
            self.metadata["error_message"] = str(exc_val)
            
        record_audit_event(self.domain, self.action, self.metadata, status=status)

import inspect
from opentelemetry import trace
from agent.core.utils import scrub_sensitive_data

tracer = trace.get_tracer(__name__)

def audit_tool(domain: str, action: str):
    """
    A decorator to automatically log tool execution metadata.

    Args:
        domain: The functional domain (e.g., 'web').
        action: The operation name (e.g., 'fetch').
    """
    def decorator(func: Callable):
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                metadata = {
                    "args": [scrub_sensitive_data(str(a)) for a in args],
                    "kwargs": {k: scrub_sensitive_data(str(v)) for k, v in kwargs.items()}
                }
                with AuditContext(domain, action, metadata):
                    with tracer.start_as_current_span(f"{domain}.{action}") as span:
                        span.set_attribute("tool.domain", domain)
                        span.set_attribute("tool.action", action)
                        return await func(*args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                metadata = {
                    "args": [scrub_sensitive_data(str(a)) for a in args],
                    "kwargs": {k: scrub_sensitive_data(str(v)) for k, v in kwargs.items()}
                }
                with AuditContext(domain, action, metadata):
                    with tracer.start_as_current_span(f"{domain}.{action}") as span:
                        span.set_attribute("tool.domain", domain)
                        span.set_attribute("tool.action", action)
                        return func(*args, **kwargs)
            return sync_wrapper
    return decorator
