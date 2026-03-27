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
Telemetry and observability utilities for ADK tools.

Provides decorators for execution time tracking and metadata logging,
and safe utilities for AST parsing with error logging.
"""

import ast
import functools
import logging
import time
from typing import Any, Callable, Dict, Optional
from agent.core.governance import log_governance_event

logger = logging.getLogger("agent.adk.telemetry")

def tool_telemetry(category: str) -> Callable:
    """
    Decorator to log tool execution metadata, duration, and governance events.

    Captures domain-specific metadata such as symbol names for search tools
    and command types for git tools.

    Args:
        category: The tool domain category (e.g., 'search', 'git').
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.perf_counter()
            
            # Extract primary metadata from arguments
            metadata = {
                "tool": func.__name__,
                "category": category,
            }

            # Domain-specific metadata extraction
            if category == "search":
                # Capture symbol name from kwargs or first positional arg
                metadata["symbol_name"] = kwargs.get("symbol_name") or kwargs.get("query")
                if not metadata["symbol_name"] and args:
                    metadata["symbol_name"] = args[0]
            
            if category == "git":
                # Capture operation type and specific paths
                metadata["git_command"] = func.__name__
                if "path" in kwargs:
                    metadata["file_path"] = str(kwargs["path"])

            try:
                result = func(*args, **kwargs)
                status = "success"
                return result
            except Exception as e:
                status = "failure"
                metadata["error"] = str(e)
                # Ensure we log the failure context before re-raising
                logger.error(f"Tool {func.__name__} failed: {e}", exc_info=True)
                raise
            finally:
                duration = time.perf_counter() - start_time
                metadata["duration_ms"] = round(duration * 1000, 2)
                
                # Log to the governance event stream for SOC2/audit trail
                log_governance_event(
                    "tool_execution",
                    f"Tool '{func.__name__}' completed in {metadata['duration_ms']}ms with status: {status}",
                    metadata=metadata
                )
                
                # Standard logging for developer visibility
                logger.info(f"[Telemetry] {func.__name__} ({category}) | {status} | {metadata['duration_ms']}ms")
        return wrapper
    return decorator

def safe_ast_parse(content: str, file_path: str) -> Optional[ast.AST]:
    """
    Attempts to parse Python content into an AST, logging a warning on failure.

    This prevents malformed files in a codebase from crashing search tools while
    maintaining visibility into parsing issues.

    Args:
        content: The file content to parse.
        file_path: Path to the file (for logging purposes).

    Returns:
        The AST tree if parsing succeeded, or None if a SyntaxError occurred.
    """
    start_time = time.perf_counter()
    try:
        tree = ast.parse(content)
        duration = (time.perf_counter() - start_time) * 1000
        logger.debug(f"AST parsed for {file_path} in {duration:.2f}ms")
        return tree
    except SyntaxError as e:
        logger.warning(
            f"Malformed Python file detected: {file_path}. "
            f"AST search skipped for this file. Error: {e.msg} at line {e.lineno}"
        )
        return None
    except Exception as e:
        logger.error(f"Unexpected error parsing AST for {file_path}: {str(e)}")
        return None
