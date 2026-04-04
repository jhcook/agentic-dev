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
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from agent.core.ai.protocols import AIProvider
from agent.core.adk.tools import ToolRegistry

logger = logging.getLogger(__name__)

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

    async def stream_interaction(self, user_prompt: str) -> AsyncGenerator[str, None]:
        """
        Stream the agent's response, handling intermediate tool calls automatically.

        Args:
            user_prompt: The user's input.

        Yields:
            Text chunks from the AI provider or intermediate progress messages.
        """
        from opentelemetry import trace
        tracer = trace.get_tracer(__name__)
        
        with tracer.start_as_current_span("AgentSession.stream_interaction") as span:
            span.set_attribute("provider", getattr(self.provider, "__class__", type(self.provider)).__name__)
            span.set_attribute("tools_count", len(self.tools))
            
            self.history.append({"role": "user", "content": user_prompt})
            
            # Native provider tool streaming loop goes here.
            # For now, we yield a simplified pass-through from the provider.
            # Deep integration with tool looping will rely on specific provider tool kwargs.
            
            async for chunk in self.provider.stream(
                prompt=user_prompt,
                system_prompt=self.system_prompt,
                tools=self.tools,
            ):
                yield chunk
