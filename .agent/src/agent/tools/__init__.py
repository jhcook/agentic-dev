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

Architecture Review (INFRA-142):
- AST-aware search utilizes lazy parsing for symbol lookup.
- Git module uses structured subprocess calls (shell=False).
- Registry integration uses domain-specific registration methods.
"""

from pathlib import Path
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


def register_domain_tools(registry: "ToolRegistry", repo_root: Path) -> None:
    """
    Registers filesystem, shell, project, and knowledge tools into the ToolRegistry.

    Each handler is wrapped in a lambda that captures ``handler`` by value at
    definition time via a default argument (``h=handler``).  Without this
    pattern all lambdas in the loop would share the *last* value of ``handler``
    (the classic Python late-binding closure bug).

    Args:
        registry: The ToolRegistry instance to populate.
        repo_root: The repository root used for path validation and sandboxing.
    """
    from agent.tools import filesystem, shell, project, knowledge  # noqa: PLC0415 – lazy to avoid circular imports

    # ------------------------------------------------------------------
    # Filesystem tools
    # ------------------------------------------------------------------
    fs_specs = [
        (
            "read_file",
            filesystem.read_file,
            "Reads a file from the repository (capped at 2000 lines).",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to repo root."},
                },
                "required": ["path"],
            },
        ),
        (
            "edit_file",
            filesystem.edit_file,
            "Rewrites the entire content of a file.",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to repo root."},
                    "content": {"type": "string", "description": "New file content."},
                },
                "required": ["path", "content"],
            },
        ),
        (
            "patch_file",
            filesystem.patch_file,
            "Replaces a specific chunk of text in a file (must match exactly once).",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to repo root."},
                    "search": {"type": "string", "description": "Text to find."},
                    "replace": {"type": "string", "description": "Replacement text."},
                },
                "required": ["path", "search", "replace"],
            },
        ),
        (
            "create_file",
            filesystem.create_file,
            "Creates a new file with the given content.",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to repo root."},
                    "content": {"type": "string", "description": "Initial file content."},
                },
                "required": ["path", "content"],
            },
        ),
        (
            "delete_file",
            filesystem.delete_file,
            "Deletes a file from the repository.",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to repo root."},
                },
                "required": ["path"],
            },
        ),
        (
            "find_files",
            filesystem.find_files,
            "Finds files matching a glob pattern (up to 100 results).",
            {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern."},
                },
                "required": ["pattern"],
            },
        ),
        (
            "move_file",
            filesystem.move_file,
            "Moves a file from one location to another within the sandbox.",
            {
                "type": "object",
                "properties": {
                    "src": {"type": "string", "description": "Source path relative to repo root."},
                    "dst": {"type": "string", "description": "Destination path relative to repo root."},
                },
                "required": ["src", "dst"],
            },
        ),
        (
            "copy_file",
            filesystem.copy_file,
            "Copies a file to a new location within the sandbox.",
            {
                "type": "object",
                "properties": {
                    "src": {"type": "string", "description": "Source path relative to repo root."},
                    "dst": {"type": "string", "description": "Destination path relative to repo root."},
                },
                "required": ["src", "dst"],
            },
        ),
        (
            "file_diff",
            filesystem.file_diff,
            "Computes a unified diff between two files.",
            {
                "type": "object",
                "properties": {
                    "path_a": {"type": "string", "description": "First file path."},
                    "path_b": {"type": "string", "description": "Second file path."},
                },
                "required": ["path_a", "path_b"],
            },
        ),
    ]

    for name, handler, desc, params in fs_specs:
        registry.register(Tool(
            name=name,
            description=desc,
            parameters=params,
            # Capture `handler` by value at loop-iteration time via default arg.
            handler=lambda *args, h=handler, **kwargs: h(*args, **kwargs, repo_root=repo_root),
            category="filesystem",
        ))

    # ------------------------------------------------------------------
    # Shell tools
    # ------------------------------------------------------------------
    shell_specs = [
        (
            "run_command",
            shell.run_command,
            "Executes a shell command in the repository root.",
            {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute."},
                    "background": {"type": "boolean", "description": "Run in the background.", "default": False},
                },
                "required": ["command"],
            },
        ),
        (
            "send_command_input",
            shell.send_command_input,
            "Sends stdin input to a running background command.",
            {
                "type": "object",
                "properties": {
                    "command_id": {"type": "string", "description": "ID of the background command."},
                    "input_text": {"type": "string", "description": "Text to send to stdin."},
                },
                "required": ["command_id", "input_text"],
            },
        ),
        (
            "check_command_status",
            shell.check_command_status,
            "Checks the status and recent output of a background command.",
            {
                "type": "object",
                "properties": {
                    "command_id": {"type": "string", "description": "ID of the background command."},
                },
                "required": ["command_id"],
            },
        ),
        (
            "interactive_shell",
            shell.interactive_shell,
            "Starts an interactive shell session (stub; not supported in non-TTY mode).",
            {
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]

    for name, handler, desc, params in shell_specs:
        registry.register(Tool(
            name=name,
            description=desc,
            parameters=params,
            # Capture `handler` by value at loop-iteration time via default arg.
            handler=lambda *args, h=handler, **kwargs: h(*args, **kwargs, repo_root=repo_root),
            category="shell",
        ))

    # ------------------------------------------------------------------
    # Project tools (INFRA-143)
    # ------------------------------------------------------------------
    project_specs = [
        (
            "match_story",
            project.match_story,
            "Matches a natural language query against available stories.",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term for matching stories."},
                },
                "required": ["query"],
            },
        ),
        (
            "read_story",
            project.read_story,
            "Reads the content of a specific story by ID.",
            {
                "type": "object",
                "properties": {
                    "story_id": {"type": "string", "description": "The ID of the story (e.g., INFRA-143)."},
                },
                "required": ["story_id"],
            },
        ),
        (
            "read_runbook",
            project.read_runbook,
            "Reads the implementation runbook for a specific story.",
            {
                "type": "object",
                "properties": {
                    "story_id": {"type": "string", "description": "The ID of the story whose runbook to read."},
                },
                "required": ["story_id"],
            },
        ),
        (
            "list_stories",
            project.list_stories,
            "Lists available story IDs in the repository.",
            {"type": "object", "properties": {}},
        ),
        (
            "list_workflows",
            project.list_workflows,
            "Lists available automated workflows.",
            {"type": "object", "properties": {}},
        ),
        (
            "fix_story",
            project.fix_story,
            "Applies an update or correction to a story document.",
            {
                "type": "object",
                "properties": {
                    "story_id": {"type": "string", "description": "ID of the story to fix."},
                    "update": {"type": "string", "description": "Corrective content to apply."},
                },
                "required": ["story_id", "update"],
            },
        ),
        (
            "list_capabilities",
            project.list_capabilities,
            "Lists all available tool capabilities and their descriptions.",
            {"type": "object", "properties": {}},
        ),
    ]

    for name, handler, desc, params in project_specs:
        registry.register(Tool(
            name=name,
            description=desc,
            parameters=params,
            handler=lambda *args, h=handler, **kwargs: h(*args, **kwargs, repo_root=repo_root, registry=registry),
            category="project",
        ))

    # ------------------------------------------------------------------
    # Knowledge tools (INFRA-143)
    # ------------------------------------------------------------------
    knowledge_specs = [
        (
            "read_adr",
            knowledge.read_adr,
            "Reads an Architecture Decision Record (ADR) by ID.",
            {
                "type": "object",
                "properties": {
                    "adr_id": {"type": "string", "description": "The numeric ID or name of the ADR."},
                },
                "required": ["adr_id"],
            },
        ),
        (
            "read_journey",
            knowledge.read_journey,
            "Reads a User Journey definition document.",
            {
                "type": "object",
                "properties": {
                    "journey_id": {"type": "string", "description": "The Journey ID (e.g. JRN-072)."},
                },
                "required": ["journey_id"],
            },
        ),
        (
            "search_knowledge",
            knowledge.search_knowledge,
            "Searches documentation and history using vector similarity.",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language search query."},
                },
                "required": ["query"],
            },
        ),
    ]

    for name, handler, desc, params in knowledge_specs:
        registry.register(Tool(
            name=name,
            description=desc,
            parameters=params,
            handler=lambda *args, h=handler, **kwargs: h(*args, **kwargs, repo_root=repo_root),
            category="knowledge",
        ))
