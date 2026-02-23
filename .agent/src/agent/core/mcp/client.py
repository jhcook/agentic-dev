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
                    try:
                        timeout_sec = float(os.environ.get("AGENT_MCP_TIMEOUT", 15.0))
                        async def _init_and_list():
                            await session.initialize()
                            return await session.list_tools()
                        result = await asyncio.wait_for(_init_and_list(), timeout=timeout_sec)
                    except asyncio.TimeoutError:
                        logger.error(f"MCP list_tools timed out after {timeout_sec} seconds.")
                        raise RuntimeError("list_tools timed out. The server might be unreachable or hanging due to network/proxy issues.")
                    
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
                env=self._full_env
            )
            with open(os.devnull, "w") as devnull:
                async with stdio_client(server_params, errlog=devnull) as (read, write):
                    async with ClientSession(read, write) as session:
                        try:
                            timeout_sec = float(os.environ.get("AGENT_MCP_TIMEOUT", 15.0))
                            async def _init_and_call():
                                await session.initialize()
                                return await session.call_tool(name, arguments)
                            result = await asyncio.wait_for(
                                _init_and_call(), timeout=timeout_sec
                            )
                            return result
                        except asyncio.TimeoutError:
                            logger.error(f"MCP tool call '{name}' timed out after {timeout_sec} seconds.")
                            raise RuntimeError(f"Tool call '{name}' timed out. The server might be unreachable or hanging due to network/proxy issues.")

    async def get_context(self, query: str) -> str:
        """
        Request context from the active MCP service (e.g., NotebookLM).
        """
        from agent.core.config import config
        from agent.db.client import get_all_artifacts_content
        from opentelemetry import trace
        
        try:
            state_docs = get_all_artifacts_content("notebooklm_state")
            state = {}
            if state_docs and state_docs[0].get("content"):
                try:
                    state = json.loads(state_docs[0]["content"])
                except Exception:
                    pass
                    
            notebook_id = state.get("notebook_id")
            if not notebook_id:
                raise RuntimeError("notebook_id not found in NotebookLM state.")
                
            logger.debug(f"Querying NotebookLM MCP for context: {query}")
            
            tracer = trace.get_tracer(__name__)
            
            @tracer.start_as_current_span("mcp.query_notebooklm_context")
            async def query_notebooklm_context(q: str, nid: str) -> str:
                span = trace.get_current_span()
                span.set_attribute("notebook_id", nid)
                span.set_attribute("query", q)
                result = await self.call_tool("notebook_query", {
                    "notebook_id": nid,
                    "query": q
                })
                # Check for standard prompt responses vs actual objects depending on Tool response
                return "\n".join([c.text for c in result.content if hasattr(c, "text")])
                
            return await query_notebooklm_context(query, notebook_id)
            
        except Exception as e:
            logger.debug(f"NotebookLM context retrieval failed, triggering fallback: {e}")
            raise RuntimeError(f"MCP Client integration failed: {e}")
