# STORY-ID: INFRA-098

## State

PROPOSED

## Goal Description

Unify the Agent Console (TUI) and the Voice Agent interface layers into a single `AgentSession` that uses the protocol-based `AIProvider` interface. This eliminates the dependency on `AgentExecutor` for the TUI and `LangGraph` for the Voice Agent, centralizing tool execution and context management, and standardizing tool definitions to a single JSON Schema format.

## Linked Journeys

- JRN-072: Terminal Console TUI Chat
- JRN-023: Voice Logic Orchestration
- JRN-031: Voice Agent Tool Integration

## Panel Review Findings

(Manual Runbook - Panel Skipped)

## Codebase Introspection

### Targeted File Contents (from source)
Checked `agent.core.adk.tools`, `backend.voice.tools.registry`, `agent.tui.agentic`, and `backend.voice.orchestrator`.

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| `tests/test_tui_agentic.py` | `LocalToolClient` | `AgentSession` integration | Update to mock `AgentSession` |
| `tests/backend/voice/test_orchestrator.py` | `create_react_agent` | `AgentSession` | Update to assert session stream |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| TUI Tools | `agent.core.adk.tools` | `make_interactive_tools` | Yes, adapt to JSON Schema |
| Voice Tools | `backend.voice.tools.registry` | `BaseTool` array | Yes, adapt to JSON Schema |

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Remove `langgraph` dependency from `backend.voice.orchestrator`.
- [ ] Deprecate `AgentExecutor` in the TUI stack.

## Implementation Steps

### Step 1: Create the unified AgentSession interface

#### [NEW] .agent/src/agent/core/session.py

```python
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

```

### Step 2: Refactor TUI tool generation to output JSON Schema

#### [MODIFY] .agent/src/agent/tui/agentic.py

```
<<<SEARCH
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
===
@dataclass
class _Tool:
    """Lightweight tool descriptor matching JSON Schema tool interface."""
    name: str
    description: str
    inputSchema: Dict[str, Any]


@dataclass
class _ToolResult:
    """Lightweight result wrapper."""
    content: str


class LocalToolClient:
    """Adapts local Python tool functions to the AgentSession interface.

    This wraps make_tools() + make_interactive_tools() from agent.core.adk.tools,
    outputting unified JSON schemas.
    """

    def __init__(
        self, 
        repo_root: Path, 
        on_output: Optional[Callable[[str], None]] = None,
        on_tool_approval: Optional[Callable[[str, str], Any]] = None,
    ):
>>>
```

### Step 3: Refactor Voice tool registry to output JSON schemas

#### [MODIFY] .agent/src/backend/voice/tools/registry.py

```
<<<SEARCH
def get_all_tools():
    """
    Return a list of all initialized tools for the agent.
    Includes core tools and dynamically loaded custom tools.
    """
===
def get_all_tools():
    """
    Return a list of all initialized Langchain BaseTools.
    Includes core tools and dynamically loaded custom tools.
    """
>>>
```

```
<<<SEARCH
    return base_tools
===
    return base_tools

def get_unified_tools() -> tuple[list[dict], dict]:
    """
    Returns tools as JSON Schemas and a handler dictionary for AgentSession.
    """
    base_tools = get_all_tools()
    schemas = []
    handlers = {}
    
    for tool in base_tools:
        # Convert Langchain BaseTool to JSON schema format
        schema = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
            }
        }
        
        if hasattr(tool, "args_schema") and tool.args_schema:
            schema["function"]["parameters"] = tool.args_schema.schema()
            
        schemas.append(schema)
        # Note: In a real async environment we would wrap `tool.arun` or `tool.run`
        handlers[tool.name] = tool.run
        
    return schemas, handlers
>>>
```

### Step 4: Update Voice Orchestrator to use AgentSession

#### [MODIFY] .agent/src/backend/voice/orchestrator.py

```
<<<SEARCH
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import ToolMessage, AIMessage
from opentelemetry import trace
from prometheus_client import Counter, Histogram

from backend.speech.factory import get_voice_providers
from agent.core.config import config
from agent.core.secrets import get_secret
===
from opentelemetry import trace
from prometheus_client import Counter, Histogram

from agent.core.session import AgentSession
from agent.core.ai.service import AIService
from backend.speech.factory import get_voice_providers
from backend.voice.tools.registry import get_unified_tools
from agent.core.config import config
from agent.core.secrets import get_secret
>>>
```

## Verification Plan

### Automated Tests

- [ ] `uv run pytest .agent/tests`

### Manual Verification

- [ ] Run `agent console` and execute a simple query.
- [ ] Start `agent admin` voice capabilities and trigger a dynamic tool creation. Verify both engines use the custom tool seamlessly.

## Definition of Done

### Documentation

- [x] CHANGELOG.md updated

### Observability

- [ ] Logs are structured and free of PII
- [ ] New structured `extra=` dicts added if new logging added

### Testing

- [ ] All existing tests pass

## Copyright

Copyright 2026 Justin Cook
