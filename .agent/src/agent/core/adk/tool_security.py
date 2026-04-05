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

"""Tool security module.

Provides argument validation, config sanitization, and OpenTelemetry-instrumented
tool execution tracking (AC-7 / ADR-046).
"""

import contextlib
import time
from typing import Any, Dict, Iterator, List, Optional

from opentelemetry import trace
from pydantic import ValidationError

from agent.core.logger import get_logger

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)


def validate_tool_args(tool_name: str, args: Dict[str, Any], schema: Any) -> bool:
    """Strictly validate tool arguments against the provided schema.

    Args:
        tool_name: The name of the tool being called.
        args: The arguments passed to the tool.
        schema: The pydantic model or schema object for validation.

    Returns:
        bool: True if valid, False otherwise.
    """
    with tracer.start_as_current_span("tool_security.validate_tool_args") as span:
        span.set_attribute("tool.name", tool_name)
        if not schema:
            logger.warning(f"No schema found for tool {tool_name}. Blocking execution for safety.")
            span.set_attribute("tool.validation.result", "blocked_no_schema")
            return False
        try:
            # Ensure we are using the pydantic model to validate the raw dict
            if hasattr(schema, 'model_validate'):
                schema.model_validate(args)
            elif hasattr(schema, 'parse_obj'):
                schema.parse_obj(args)
            else:
                schema(**args)
            span.set_attribute("tool.validation.result", "passed")
            return True
        except (ValidationError, TypeError, ValueError) as e:
            logger.error(f"Schema validation failed for tool {tool_name}: {e}")
            span.set_attribute("tool.validation.result", "failed")
            span.record_exception(e)
            return False


def secure_config_injection(config: Dict[str, Any], interface_type: str) -> Dict[str, Any]:
    """Sanitize RunnableConfig based on interface type to prevent privilege escalation.

    Args:
        config: The RunnableConfig dictionary to sanitize.
        interface_type: The type of interface ('voice' or 'console').

    Returns:
        Dict[str, Any]: The sanitized configuration dictionary.
    """
    with tracer.start_as_current_span("tool_security.secure_config_injection") as span:
        span.set_attribute("interface.type", interface_type)
        # Whitelist of allowed configurable keys per interface
        # This prevents cross-interface spoofing or unauthorized param injection
        SAFE_KEYS = {
            "voice": ["session_id", "voice_settings", "stream_id", "is_streaming", "language"],
            "console": ["terminal_size", "theme", "history_limit", "user_env", "interactive"]
        }
        
        if "configurable" not in config:
            return config
                
        allowed = SAFE_KEYS.get(interface_type, [])
        original_configurable = config.get("configurable", {})
        
        sanitized_configurable = {
            k: v for k, v in original_configurable.items() 
            if k in allowed
        }
        
        # Security logging for stripped keys
        removed_keys = set(original_configurable.keys()) - set(sanitized_configurable.keys())
        if removed_keys:
            logger.warning(f"Stripped unauthorized configurable keys from {interface_type} context: {removed_keys}")
            span.set_attribute("security.stripped_keys", str(removed_keys))

        config["configurable"] = sanitized_configurable
        return config


@contextlib.contextmanager
def track_tool_usage(tool_name: str, session_id: str = "") -> Iterator[trace.Span]:
    """Context manager wrapping tool execution with an OTel span (AC-7 / ADR-046).

    Emits ``tool.name``, ``session_id``, ``tool.duration_ms``, and ``tool.success``
    attributes on every tool invocation for audit logging compliance.

    Args:
        tool_name: The canonical name of the tool being invoked.
        session_id: The session identifier for audit correlation.

    Yields:
        The active OpenTelemetry ``Span`` so callers can attach extra attributes.
    """
    with tracer.start_as_current_span(f"tool.{tool_name}") as span:
        span.set_attribute("tool.name", tool_name)
        span.set_attribute("session_id", session_id)
        start = time.monotonic()
        try:
            yield span
            elapsed_ms = round((time.monotonic() - start) * 1000, 2)
            span.set_attribute("tool.success", True)
            span.set_attribute("tool.duration_ms", elapsed_ms)
            logger.info(
                "tool_execution_success",
                extra={
                    "tool.name": tool_name,
                    "session_id": session_id,
                    "duration_ms": elapsed_ms,
                },
            )
        except Exception as exc:
            elapsed_ms = round((time.monotonic() - start) * 1000, 2)
            span.record_exception(exc)
            span.set_attribute("tool.success", False)
            span.set_attribute("tool.duration_ms", elapsed_ms)
            logger.error(
                "tool_execution_error",
                extra={
                    "tool.name": tool_name,
                    "session_id": session_id,
                    "duration_ms": elapsed_ms,
                    "error": str(exc),
                },
            )
            raise
