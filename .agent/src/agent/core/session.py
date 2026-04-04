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
Unified Agent Session for managing AI interactions and tool execution.

This module provides the boundary layer between the interface (TUI/Voice)
and the underlying AI provider.
"""

import json
import logging
import time
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from opentelemetry import trace

from agent.core.ai.protocols import AIProvider
from agent.core.adk.tools import ToolRegistry

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class AgentSession:
    """Manages the context and tool execution loop for an AI agent interaction."""

    def __init__(
        self,
        provider: AIProvider,
        system_prompt: str,
        tools: List[Dict[str, Any]],
        tool_handlers: Dict[str, Callable]
    ):
        """
        Initialize the session.

        Args:
            provider: The AIProvider instance to use for generation.
            system_prompt: The system prompt defining the agent's persona.
            tools: JSON Schema definitions of available tools.
            tool_handlers: Dictionary mapping tool names to callable functions.
        """
        self.provider = provider
        self.system_prompt = system_prompt
        self.tools = tools
        self.tool_handlers = tool_handlers
        self.history: List[Dict[str, Any]] = []

    def _dispatch_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        """Dispatch a single tool call with an OpenTelemetry span (AC-7).

        Emits structured log events on success and failure for ADR-046 compliance.
        """
        handler = self.tool_handlers.get(tool_name)
        if handler is None:
            logger.warning(
                "tool_dispatch_unknown",
                extra={"tool": tool_name},
            )
            return f"[Error: unknown tool '{tool_name}']"

        with tracer.start_as_current_span(f"tool.{tool_name}") as span:
            span.set_attribute("tool.name", tool_name)
            span.set_attribute("tool.args", json.dumps(tool_args, default=str))
            start = time.monotonic()
            try:
                result = handler(**tool_args)
                elapsed_ms = (time.monotonic() - start) * 1000
                span.set_attribute("tool.success", True)
                span.set_attribute("tool.duration_ms", round(elapsed_ms, 2))
                logger.info(
                    "tool_dispatch_success",
                    extra={"tool": tool_name, "duration_ms": round(elapsed_ms, 2)},
                )
                return str(result) if result is not None else ""
            except Exception as exc:
                elapsed_ms = (time.monotonic() - start) * 1000
                span.record_exception(exc)
                span.set_attribute("tool.success", False)
                logger.error(
                    "tool_dispatch_error",
                    extra={"tool": tool_name, "error": str(exc), "duration_ms": round(elapsed_ms, 2)},
                )
                return f"[Tool error: {exc}]"

    async def stream_interaction(self, user_prompt: str) -> AsyncGenerator[str, None]:
        """Stream the agent's response, handling intermediate tool calls.

        Runs the provider's tool-use loop: the provider may return one or more
        tool-call requests before yielding the final text response. Each tool
        invocation is wrapped in an OpenTelemetry span (INFRA-146 AC-7).

        Args:
            user_prompt: The user's input.

        Yields:
            Text chunks from the AI provider or progress messages from tools.
        """
        with tracer.start_as_current_span("AgentSession.stream_interaction") as span:
            span.set_attribute(
                "provider",
                getattr(type(self.provider), "__name__", "unknown"),
            )
            span.set_attribute("tools_count", len(self.tools))

            self.history.append({"role": "user", "content": user_prompt})

            # Tool-use agentic loop: keep calling the provider until it stops
            # issuing tool calls and produces a final text response.
            MAX_TOOL_ROUNDS = 10
            for round_idx in range(MAX_TOOL_ROUNDS):
                tool_calls_this_round: List[Dict[str, Any]] = []
                text_chunks: List[str] = []

                async for chunk in self.provider.stream(
                    prompt=user_prompt,
                    system_prompt=self.system_prompt,
                    tools=self.tools,
                    history=self.history,
                ):
                    if isinstance(chunk, dict) and chunk.get("type") == "tool_call":
                        # Provider signalled a tool invocation
                        tool_calls_this_round.append(chunk)
                    elif isinstance(chunk, str):
                        text_chunks.append(chunk)
                        yield chunk

                if not tool_calls_this_round:
                    # No tool calls → final response; record and exit loop
                    final_text = "".join(text_chunks)
                    if final_text:
                        self.history.append({"role": "assistant", "content": final_text})
                    break

                # Execute each tool call and feed results back into history
                tool_results: List[Dict[str, Any]] = []
                for tc in tool_calls_this_round:
                    name = tc.get("name", "")
                    args = tc.get("arguments", {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}
                    result_text = self._dispatch_tool(name, args)
                    tool_results.append({
                        "role": "tool",
                        "name": name,
                        "content": result_text,
                    })
                    logger.debug("tool_round_complete", extra={"round": round_idx, "tool": name})

                self.history.extend(tool_results)

                # Reset user_prompt so the next provider call uses history only
                user_prompt = ""
            else:
                logger.warning(
                    "tool_loop_max_rounds_exceeded",
                    extra={"max_rounds": MAX_TOOL_ROUNDS},
                )
