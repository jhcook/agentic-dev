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
except ImportError:
    # Allow import for type checking / CLI loading without dependency
    ClientSession = Any
    StdioServerParameters = Any
    stdio_client = Any

logger = logging.getLogger(__name__)

@dataclass
class Tool:
    name: str
    description: str
    inputSchema: Dict[str, Any]

class MCPClient:
    def __init__(self, command: str, args: List[str], env: Optional[Dict[str, str]] = None):
        self.command = command
        self.args = args
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
        
        async with stdio_client(server_params) as (read, write):
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

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Call a specific tool on the server."""
        server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=self._full_env
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)
                return result
