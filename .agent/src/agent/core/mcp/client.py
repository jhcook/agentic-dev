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

import asyncio
import json
import logging
import os
import shutil
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.types import CallToolResult
except ImportError as e:
    # Allow import for type checking / CLI loading without dependency
    import sys
    print(f"[WARN] Failed to import mcp: {e}", file=sys.stderr)
    ClientSession = Any
    StdioServerParameters = Any
    stdio_client = Any
    CallToolResult = Any

logger = logging.getLogger(__name__)

@dataclass
class Tool:
    name: str
    description: str
    inputSchema: Dict[str, Any]

class MCPClient:
    def __init__(self, command: str = "notebooklm-mcp", args: List[str] = None, env: Optional[Dict[str, str]] = None):
        self.command = command
        self.args = args or []
        self.env = env or {}
        # Merge with current env to ensure PATH is correct
        self._full_env = os.environ.copy()
        self._full_env.update(self.env)

    async def list_tools(self) -> List[Tool]:
        """List available tools from the server."""
        server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=self._full_env
        )
        
        # Redirect stderr to devnull to prevent FastMCP splash screens and warnings from polluting our CLI
        with open(os.devnull, "w") as devnull:
            async with stdio_client(server_params, errlog=devnull) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    return [
                    Tool(
                        name=t.name,
                        description=t.description,
                        inputSchema=t.inputSchema
                    ) for t in result.tools
                ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> CallToolResult:
        """Call a specific tool on the server."""
        from opentelemetry import trace
        tracer = trace.get_tracer(__name__)
        
        with tracer.start_as_current_span("mcp.call_tool") as span:
            span.set_attribute("tool_name", name)
            server_params = StdioServerParameters(
                command=self.command,
                args=self.args,
                env=self.env
            )
            with open(os.devnull, "w") as devnull:
                async with stdio_client(server_params, errlog=devnull) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(name, arguments)
                        return result

    def get_context(self, query: str) -> str:
        """
        Request context from the active MCP service (e.g., NotebookLM).
        """
        from agent.core.config import config
        state_file = config.agent_dir / "cache" / "notebooklm_state.json"
        
        try:
            if not state_file.exists():
                raise RuntimeError("NotebookLM state file not found.")
                
            with open(state_file, "r") as f:
                state = json.load(f)
                
            notebook_id = state.get("notebook_id")
            if not notebook_id:
                raise RuntimeError("notebook_id not found in NotebookLM state.")
                
            logger.debug(f"Querying NotebookLM MCP for context: {query}")
            
            async def _query():
                result = await self.call_tool("mcp_notebooklm_notebook_query", {
                    "notebook_id": notebook_id,
                    "query": query
                })
                # Check for standard prompt responses vs actual objects depending on Tool response
                return "\n".join([c.text for c in result.content if hasattr(c, "text")])
                
            return asyncio.run(_query())
            
        except Exception as e:
            logger.debug(f"NotebookLM context retrieval failed, triggering fallback: {e}")
            raise RuntimeError(f"MCP Client integration failed: {e}")
