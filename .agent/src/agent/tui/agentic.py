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

"""Agentic tool-calling loop for the Console TUI.

This module bridges the TUI and the core AgentExecutor,
translating executor events into TUI callbacks.

It uses a LocalToolClient to provide local Python tools
(read_file, edit_file, run_command, etc.) to the AgentExecutor
instead of an MCP server connection.
"""

from opentelemetry import trace
import asyncio
import inspect
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from agent.core.ai import ai_service
from agent.core.engine.executor import AgentExecutor

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

FUNCTION_CALLING_PROVIDERS = {"gemini", "vertex", "openai", "anthropic"}


def supports_function_calling(provider: str) -> bool:
    """Check if a provider supports native function calling."""
    return provider in FUNCTION_CALLING_PROVIDERS


@dataclass
class _Tool:
    """Lightweight tool descriptor matching MCPClient.Tool interface."""
    name: str
    description: str
    inputSchema: Dict[str, Any]


@dataclass
class _ToolResult:
    """Lightweight result matching MCPClient.CallToolResult interface."""
    content: str


class LocalToolClient:
    """Adapts local Python tool functions to the AgentExecutor's interface.

    The AgentExecutor expects an object with:
      - async list_tools() -> List[Tool]
      - async call_tool(name, arguments) -> result with .content

    This wraps make_tools() + make_interactive_tools() from agent.core.adk.tools.
    """

    def __init__(
        self, 
        repo_root: Path, 
        on_output: Optional[Callable[[str], None]] = None,
        on_tool_approval: Optional[Callable[[str, str], Any]] = None,
    ):
        from agent.core.adk.tools import make_tools, make_interactive_tools

        self.on_tool_approval = on_tool_approval

        self._dispatch: Dict[str, Callable] = {}
        self._tool_metadata: List[_Tool] = []

        # Register read-only tools
        for fn in make_tools(repo_root):
            self._register(fn)

        # Register interactive tools
        for fn in make_interactive_tools(repo_root, on_output=on_output):
            self._register(fn)

    def _register(self, fn: Callable) -> None:
        """Register a tool function and extract its schema from signature."""
        name = fn.__name__
        description = fn.__doc__ or f"Tool: {name}"
        sig = inspect.signature(fn)

        # Build a JSON Schema from the function signature
        properties = {}
        required = []
        for pname, param in sig.parameters.items():
            prop: Dict[str, Any] = {"type": "string"}
            if param.annotation == int:
                prop["type"] = "integer"
            elif param.annotation == bool:
                prop["type"] = "boolean"
            if param.default is inspect.Parameter.empty:
                required.append(pname)
            properties[pname] = prop

        schema = {
            "type": "object",
            "properties": properties,
            "required": required,
        }

        self._dispatch[name] = fn
        self._tool_metadata.append(_Tool(
            name=name,
            description=description.strip(),
            inputSchema=schema,
        ))

    async def list_tools(self) -> List[_Tool]:
        """Return tool descriptors for the executor's prompt."""
        return self._tool_metadata

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> _ToolResult:
        """Execute a tool by name and return its result."""
        fn = self._dispatch.get(name)
        if not fn:
            return _ToolResult(content=f"Error: Tool '{name}' not found.")

        try:
            # Smart argument mapping: handle both raw strings and generic "input" keys
            sig = inspect.signature(fn)
            params = list(sig.parameters.keys())

            if isinstance(arguments, str):
                # Map raw string to the first parameter if there's only one
                if len(params) == 1:
                    arguments = {params[0]: arguments}
            elif isinstance(arguments, dict) and len(params) == 1:
                # If LLM sent {"input": "..."}, or similar, map to the single parameter
                pname = params[0]
                if pname not in arguments and len(arguments) == 1:
                    # Generic mapping for single-arg tools
                    val = next(iter(arguments.values()))
                    arguments = {pname: val}
                elif "input" in arguments and pname != "input":
                    # Specific fix for "input" key
                    arguments = {pname: arguments["input"]}

            if name == "run_command":
                cmd_str = arguments.get("command", "")
                if self.on_tool_approval:
                    approved = await self.on_tool_approval(name, cmd_str)
                    if not approved:
                        return _ToolResult(content="Error: User denied permission to execute command.")
                else:
                    # Fallback for non-TUI usage
                    from rich.prompt import Confirm
                    from rich.console import Console
                    c = Console()
                    c.print(f"\n[bold yellow]⚠️  Agent wants to execute:[/bold yellow] [cyan]{cmd_str}[/cyan]")
                    if not Confirm.ask("[bold red]Allow execution?[/bold red]", default=False):
                        return _ToolResult(content="Error: User denied permission to execute command.")

            result = await asyncio.to_thread(fn, **arguments)
            return _ToolResult(content=str(result))
        except Exception as e:
            logger.error(f"Tool '{name}' failed: {e}", exc_info=True)
            return _ToolResult(content=f"Error executing {name}: {e}")


async def run_agentic_loop(
    system_prompt: str,
    user_prompt: str,
    messages: List[Dict[str, str]],
    repo_root: Path,
    provider: str,
    model: Optional[str] = None,
    on_thought: Optional[Callable[[str, int], None]] = None,
    on_tool_call: Optional[Callable[[str, Dict[str, Any], int], None]] = None,
    on_tool_result: Optional[Callable[[str, str, int], None]] = None,
    on_final_answer: Optional[Callable[[str], None]] = None,
    on_error: Optional[Callable[[str], None]] = None,
    on_output: Optional[Callable[[str], None]] = None,
    on_tool_approval: Optional[Callable[[str, str], Any]] = None,
) -> str:
    """
    Run the agentic loop using AgentExecutor with local tools.

    Args:
        system_prompt: The base system instruction for the agent.
        user_prompt: The user's most recent message.
        messages: The full conversation history for context.
        repo_root: The root directory of the repository.
        provider: The AI provider to use.
        model: Optional model override.
        on_thought: Callback for when the agent thinks.
        on_tool_call: Callback when a tool is called.
        on_tool_result: Callback with the result of a tool call.
        on_final_answer: Callback for the final answer.
        on_error: Callback for any errors.
        on_output: Callback for streaming run_command output.
        on_tool_approval: Async callback to prompt user for permission to execute a tool.

    Returns:
        The final answer from the agent.
    """
    with tracer.start_as_current_span("agent.run_agentic_loop"):
        # 1. Configure the AI service
        if ai_service.provider != provider:
            ai_service.set_provider(provider)
        if model:
            ai_service.models[provider] = model

        # 2. Create a local tool client (no MCP server needed)
        tool_client = LocalToolClient(
            repo_root=repo_root, 
            on_output=on_output,
            on_tool_approval=on_tool_approval
        )

        # 3. Create the executor with local tools
        executor = AgentExecutor(
            llm=ai_service,
            mcp_client=tool_client,
            system_prompt=system_prompt,
            model=model,
        )

        # 4. Build context from conversation history
        history_str = "\n".join(
            f"{msg['role']}: {msg['content']}" for msg in messages
        )
        full_user_prompt = (
            f"Previous conversation:\n{history_str}\n\nNew task: {user_prompt}"
            if messages
            else user_prompt
        )

        final_answer = ""
        step = 1

        # 5. Run the executor and handle streamed events
        try:
            async for event in executor.run(user_prompt=full_user_prompt):
                event_type = event.get("type")

                if event_type == "thought":
                    if on_thought and "content" in event:
                        on_thought(str(event["content"]), step)

                elif event_type == "tool_call":
                    if on_tool_call and "tool" in event and "input" in event:
                        tool_input = event["input"]
                        # Align UI display with smart mapping logic
                        fn = tool_client._dispatch.get(event["tool"])
                        if fn:
                            sig = inspect.signature(fn)
                            params = list(sig.parameters.keys())
                            if isinstance(tool_input, str) and len(params) == 1:
                                tool_input = {params[0]: tool_input}
                            elif isinstance(tool_input, dict) and len(params) == 1:
                                pname = params[0]
                                if pname not in tool_input and len(tool_input) == 1:
                                    tool_input = {pname: next(iter(tool_input.values()))}
                                elif "input" in tool_input and pname != "input":
                                    tool_input = {pname: tool_input["input"]}
                        
                        args = tool_input if isinstance(tool_input, dict) else {"input": str(tool_input)}
                        on_tool_call(event["tool"], args, step)

                elif event_type == "tool_result":
                    if on_tool_result and "tool" in event and "output" in event:
                        on_tool_result(event["tool"], str(event["output"]), step)
                    step += 1

                elif event_type == "final_answer":
                    if "content" in event:
                        final_answer = str(event["content"])
                        if on_final_answer:
                            on_final_answer(final_answer)
                    break

                elif event_type == "error":
                    if on_error and "content" in event:
                        on_error(str(event["content"]))
                    break

        except Exception as e:
            import traceback
            with open('/tmp/executor_error.log', 'w') as f:
                traceback.print_exc(file=f)
            logger.error(f"AgentExecutor failed: {e}", exc_info=True)
            if on_error:
                on_error(f"An unexpected error occurred: {e}")

        return final_answer
