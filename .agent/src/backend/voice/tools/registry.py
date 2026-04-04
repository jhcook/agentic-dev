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
Voice tool registry — delegates to ToolRegistry (INFRA-146 AC-4).

This module replaces the previous LangChain BaseTool aggregator with a
ToolRegistry-backed implementation. All tool functions are plain Python
callables; schema introspection uses inspect rather than LangChain.
"""

import inspect
import logging
import os
import importlib
import sys
from pathlib import Path
from typing import Callable, List, Tuple, Dict, Any

from agent.core.adk.tools import ToolRegistry

logger = logging.getLogger(__name__)


def get_all_tools(repo_root: Path | None = None) -> List[Callable]:
    """Return all voice-layer tools as plain callables via ToolRegistry.

    Falls back to graceful degradation if ToolRegistry is unavailable.
    Custom tools from the ``custom/`` directory are appended after the
    canonical registry list.
    """
    registry = ToolRegistry(repo_root=repo_root)
    tools: List[Callable] = list(registry.list_tools(all=True))

    # Append dynamically-loaded custom tools from this directory.
    custom_dir = Path(os.path.dirname(__file__)) / "custom"
    if custom_dir.exists():
        for filename in sorted(custom_dir.iterdir()):
            if filename.suffix != ".py" or filename.stem.startswith("__"):
                continue
            module_name = f"backend.voice.tools.custom.{filename.stem}"
            try:
                if module_name in sys.modules:
                    module = importlib.reload(sys.modules[module_name])
                else:
                    module = importlib.import_module(module_name)
                for _, obj in inspect.getmembers(module, inspect.isfunction):
                    if obj not in tools:
                        tools.append(obj)
            except Exception as exc:
                logger.warning("custom_tool_load_error", extra={"file": filename.name, "error": str(exc)})

    return tools


def _build_schema(fn: Callable) -> Dict[str, Any]:
    """Introspect a plain callable and return an OpenAI-compatible function schema."""
    sig = inspect.signature(fn)
    doc = (fn.__doc__ or "").strip()
    parameters: Dict[str, Any] = {"type": "object", "properties": {}, "required": []}

    for name, param in sig.parameters.items():
        prop: Dict[str, Any] = {"type": "string"}
        if param.annotation is not inspect.Parameter.empty:
            ann = param.annotation
            if ann is int:
                prop["type"] = "integer"
            elif ann is bool:
                prop["type"] = "boolean"
        parameters["properties"][name] = prop
        if param.default is inspect.Parameter.empty:
            parameters["required"].append(name)

    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": doc,
            "parameters": parameters,
        },
    }


def get_unified_tools(
    repo_root: Path | None = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Callable]]:
    """Return (schemas, handlers) for the voice orchestrator.

    ``schemas`` is a list of OpenAI-compatible function-call JSON schemas.
    ``handlers`` maps each tool name to its callable for dispatch.
    """
    tools = get_all_tools(repo_root=repo_root)
    schemas: List[Dict[str, Any]] = []
    handlers: Dict[str, Callable] = {}

    for tool in tools:
        try:
            schemas.append(_build_schema(tool))
            handlers[tool.__name__] = tool
        except Exception as exc:
            logger.warning("tool_schema_build_error", extra={"tool": getattr(tool, "__name__", "?"), "error": str(exc)})

    return schemas, handlers
