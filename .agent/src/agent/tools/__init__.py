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
Core tool registry and foundational models for agentic tools.
"""

from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field
from agent.core.governance import log_governance_event


class ToolRegistryError(Exception):
    """
    Raised when a tool registry operation fails.
    """
    pass


class ToolResult(BaseModel):
    """
    Standard container for the result of a tool execution.
    """
    success: bool = Field(..., description="Whether the tool execution succeeded")
    output: Optional[Any] = Field(None, description="The output data from the tool")
    error: Optional[str] = Field(None, description="The error message if the tool failed")


class Tool(BaseModel):
    """
    Definition of a tool that can be registered and executed by an agent.
    """
    name: str = Field(..., description="Unique name of the tool")
    description: str = Field(..., description="Description of what the tool does")
    parameters: Dict[str, Any] = Field(..., description="JSON schema of the tool parameters")
    handler: Callable[..., Any] = Field(..., description="The function to execute")
    category: str = Field("general", description="The domain category of the tool (e.g., filesystem, shell)")
    restricted: bool = Field(True, description="Whether the tool requires explicit authorization to run")


class ToolRegistry:
    """
    Central registry for managing agent tools.
    """

    def __init__(self) -> None:
        """
        Initialize the registry with an empty tool map.
        """
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """
        Registers a new tool in the registry.

        Args:
            tool: The Tool instance to register.

        Raises:
            ToolRegistryError: If a tool with the same name already exists.
        """
        if tool.name in self._tools:
            raise ToolRegistryError(f"Tool with name '{tool.name}' already registered.")
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Tool:
        """
        Retrieves a tool by its name.

        Args:
            name: The name of the tool to retrieve.

        Returns:
            The requested Tool instance.

        Raises:
            ToolRegistryError: If the tool is not found.
        """
        if name not in self._tools:
            raise ToolRegistryError(f"Tool '{name}' not found.")
        return self._tools[name]

    def list_tools(self, category: Optional[str] = None) -> List[Tool]:
        """
        Lists tools, optionally filtered by category.

        Args:
            category: Optional category name to filter by.

        Returns:
            A list of registered Tool instances.
        """
        if category:
            return [t for t in self._tools.values() if t.category == category]
        return list(self._tools.values())

    def unrestrict_tool(self, name: str) -> None:
        """
        Removes the restriction flag from a tool and logs the audit event.

        Args:
            name: The name of the tool to unrestrict.

        Raises:
            ToolRegistryError: If the tool is not found.
        """
        if name not in self._tools:
            raise ToolRegistryError(f"Tool '{name}' not found.")

        self._tools[name].restricted = False
        log_governance_event(
            "tool_unrestrict",
            f"Tool '{name}' has been unrestricted for general use."
        )
