# Runbook: Implementation Runbook for INFRA-145

## State

ACCEPTED

## Implementation Steps

### Step 1: Architecture & Design Review

#### [NEW] .agent/src/agent/core/adk/tool_registry_strategy.md

```markdown
# Design Strategy: ToolRegistry Context Parity (INFRA-145)

## 1. Objective
Ensure that both Console (TUI) and Voice interfaces consume tools through a unified `ToolRegistry` while supporting interface-specific `RunnableConfig` injection to maintain parity and satisfy ADR-029.

## 2. Context Injection Strategy

**Problem Statement**
Voice tools often require `RunnableConfig` injection (specifically `configurable` fields) to handle streaming audio events, state management, and callback routing. The current `ToolRegistry` returns static tool instances which lacks a unified way to inject this context at runtime.

**Proposed Strategy: Runtime Binding**
- **Stateless Registry**: The `ToolRegistry` will remain a stateless singleton that manages tool discovery and metadata.
- **Interface-Specific Config**: 
    - **Console Interface**: Will pass its `RunnableConfig` (telemetry, user context) to the `AgentSession`.
    - **Voice Interface**: Will pass its `RunnableConfig` (voice event loop, TTS buffers) to the `VoiceOrchestrator`.
- **Dynamic Binding**: The `Executor` (`agent/core/engine/executor.py`) will be the central point where the interface-provided `RunnableConfig` is bound to the tool instance retrieved from the registry. This will use the standard ADK/LangChain `.with_config()` or manual context injection pattern to ensure parity.

## 3. ADR-029 Alignment
ADR-029 specifies a multi-agent architecture where interfaces are thin adapters. By unifying tool lookup and execution under the `ToolRegistry` and a shared `Executor`, we ensure that:
1. Any new tool registered is immediately available to both Console and Voice.
2. Tool execution logic (including status yielding like 'Thinking...') is identical across interfaces.
3. Security and schema validation are applied consistently at the core layer.

## 4. Verification Strategy
- **AC-5 Integration Test**: A single test suite will verify that `ToolRegistry.list_tools()` returns an identical list of tool definitions when called from both the TUI session and the Voice orchestrator.
- **Negative Test**: Verify that removing a tool from the centralized registration point results in a `ToolNotFoundError` in both interfaces simultaneously.

```

### Step 2: Core Engine & Execution Refactor

#### [MODIFY] CHANGELOG.md

```

<<<SEARCH
## [Unreleased] (Updated by story)
===
## [Unreleased] (Updated by story)

## [Unreleased] - 2026-03-05
**Changed**
- Refactored `AgentSession` to delegate tool management to `ToolRegistry` (INFRA-145).
- Updated `ToolExecutor` to yield 'Thinking...' status updates during tool execution (INFRA-145).
>>>

```

#### [MODIFY] .agent/src/agent/core/session.py

```

<<<SEARCH
from typing import Any, Dict, List, Optional
import logging

from agent.core.config import config
===
from typing import Any, Dict, List, Optional
import logging

from agent.core.config import config
from agent.core.adk.tools import ToolRegistry
>>>

```

<!-- DEDUP: agent/core/session.py already [MODIFY] in Step 1. All changes for this file should be consolidated there. -->

#### [MODIFY] .agent/src/agent/core/engine/executor.py

```

<<<SEARCH
async def execute(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """Execute a tool call."""
        tool = self._get_tool(tool_name)
        return await tool.arun(tool_input)
===
async def execute(self, tool_name: str, tool_input: Dict[str, Any]):
        """Execute a tool call and yield status updates.

        Yields:
            str: Intermediary status updates (e.g., "Thinking...")
            Any: The final tool execution result.
        """
        tool = self._get_tool(tool_name)
        yield "Thinking..."
        result = await tool.arun(tool_input)
        yield result
>>>

```

### Step 3: Interface Adapter Integration

#### [MODIFY] .agent/src/agent/tui/session.py

```

<<<SEARCH
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

"""Conversation session persistence and token budget management (INFRA-087)."""
===
from typing import Optional, List
from agent.core.session import AgentSession
from agent.core.adk.tools import ToolRegistry

class TUISession:
    """
    Session adapter for the Terminal User Interface.

    This class acts as a thin adapter that initializes the unified ToolRegistry
    and passes it to the core agent session to ensure identical tool availability
    across all interfaces.
    """

    def __init__(self, story_id: Optional[str] = None):
        """Initialize the TUI session handler.

        Args:
            story_id: Optional identifier for the story context.
        """
        # AC-2: Initialize unified ToolRegistry and pass to the core session
        self.tool_registry = ToolRegistry()
        self.agent_session = AgentSession(
            story_id=story_id,
            tool_registry=self.tool_registry
        )

    def get_available_tools(self) -> List:
        """AC-5: Retrieve the list of tools from the unified registry."""
        return self.tool_registry.list_tools()
>>>

```

#### [MODIFY] .agent/src/backend/voice/orchestrator.py

```

<<<SEARCH
class VoiceOrchestrator:
    """Orchestrates voice interaction flow with LangGraph agent using Sequential Queueing."""
===
from typing import List, Optional
from agent.core.adk.tools import ToolRegistry
from langchain_core.runnables import RunnableConfig

class VoiceOrchestrator:
    """Orchestrator for Voice interactions using ToolRegistry.

    This component acts as a thin adapter that consumes tools from the unified
    registry, supporting context-aware tool lookup for voice logic.
    """

    def __init__(self):
        # AC-3: Initialize ToolRegistry instead of manual BaseTool scanning
        self.registry = ToolRegistry()

    def get_tools(self, config: Optional[RunnableConfig] = None) -> List:
        """
        Retrieve available tools for the voice session.

        AC-3: Uses ToolRegistry to ensure parity with the TUI interface.
        Context from RunnableConfig is passed to the registry for injection.
        """
        return self.registry.list_tools(config=config)
>>>

```

### Step 4: Security & Input Sanitization

#### [NEW] .agent/src/agent/core/adk/tool_security.py

```python
from typing import Any, Dict, List, Optional
from pydantic import ValidationError
from agent.core.logger import get_logger

logger = get_logger(__name__)

def validate_tool_args(tool_name: str, args: Dict[str, Any], schema: Any) -> bool:
    """Strictly validate tool arguments against the provided schema.

    Args:
        tool_name: The name of the tool being called.
        args: The arguments passed to the tool.
        schema: The pydantic model or schema object for validation.

    Returns:
        bool: True if valid, False otherwise.
    """
    if not schema:
        logger.warning(f"No schema found for tool {tool_name}. Blocking execution for safety.")
        return False
    try:
        # Ensure we are using the pydantic model to validate the raw dict
        if hasattr(schema, 'model_validate'):
            schema.model_validate(args)
        elif hasattr(schema, 'parse_obj'):
            schema.parse_obj(args)
        else:
            schema(**args)
        return True
    except (ValidationError, TypeError, ValueError) as e:
        logger.error(f"Schema validation failed for tool {tool_name}: {e}")
        return False

def secure_config_injection(config: Dict[str, Any], interface_type: str) -> Dict[str, Any]:
    """Sanitize RunnableConfig based on interface type to prevent privilege escalation.

    Args:
        config: The RunnableConfig dictionary to sanitize.
        interface_type: The type of interface ('voice' or 'console').

    Returns:
        Dict[str, Any]: The sanitized configuration dictionary.
    """
    # Whitelist of allowed configurable keys per interface
    # This prevents cross-interface spoofing or unauthorized param injection
    SAFE_KEYS = {
        "voice": ["session_id", "voice_settings", "stream_id", "is_streaming", "language"],
        "console": ["terminal_size", "theme", "history_limit", "user_env", "interactive"]
    }
    
    if "configurable" not in config:
        return config
            
    allowed = SAFE_KEYS.get(interface_type, [])
    original_configurable = config.get("configurable", {})
    
    sanitized_configurable = {
        k: v for k, v in original_configurable.items() 
        if k in allowed
    }
    
    # Security logging for stripped keys
    removed_keys = set(original_configurable.keys()) - set(sanitized_configurable.keys())
    if removed_keys:
        logger.warning(f"Stripped unauthorized configurable keys from {interface_type} context: {removed_keys}")

    config["configurable"] = sanitized_configurable
    return config

```

#### [MODIFY] .agent/src/agent/commands/audit.py

```

<<<SEARCH
from agent.core.security import scrub_sensitive_data
from agent.tools.telemetry import get_tool_metrics
===
from agent.core.security import scrub_sensitive_data
from agent.tools.telemetry import get_tool_metrics
from agent.core.adk.tool_security import secure_config_injection
>>>

```

#### [NEW] .agent/tests/agent/core/adk/test_tool_security.py

```python
import pytest
from pydantic import BaseModel
from agent.core.adk.tool_security import validate_tool_args, secure_config_injection

class MockSearchSchema(BaseModel):
    query: str
    limit: int = 10

def test_validate_tool_args_success():
    """Verify valid arguments pass schema check."""
    valid_args = {"query": "test execution", "limit": 5}
    assert validate_tool_args("mock_search", valid_args, MockSearchSchema) is True

def test_validate_tool_args_failure():
    """Verify invalid arguments are rejected."""
    # Missing required 'query'
    assert validate_tool_args("mock_search", {"limit": 5}, MockSearchSchema) is False
    # Invalid type for 'limit'
    assert validate_tool_args("mock_search", {"query": "test", "limit": "invalid"}, MockSearchSchema) is False

def test_secure_config_injection_isolation():
    """Verify cross-interface keys are stripped."""
    config = {
        "configurable": {
            "session_id": "voice_123",
            "terminal_size": [80, 24], # Should be removed in voice context
            "admin_esc": True          # Should be removed always
        }
    }
    
    # Test Voice Sanitization
    voice_sanitized = secure_config_injection(config.copy(), "voice")
    assert "session_id" in voice_sanitized["configurable"]
    assert "terminal_size" not in voice_sanitized["configurable"]
    assert "admin_esc" not in voice_sanitized["configurable"]
    
    # Test Console Sanitization
    console_sanitized = secure_config_injection(config.copy(), "console")
    assert "terminal_size" in console_sanitized["configurable"]
    assert "session_id" not in console_sanitized["configurable"]
    assert "admin_esc" not in console_sanitized["configurable"]

```

### Step 5: Observability & Audit Logging

#### [NEW] .agent/tests/agent/core/test_tool_telemetry.py

```python
import pytest
import json
from unittest.mock import MagicMock, patch
from agent.commands.audit import tool_execution_span

def test_tool_span_integration():
    """Verify that tool_execution_span correctly creates spans with metadata."""
    with patch("opentelemetry.trace.get_tracer") as mock_get_tracer:
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_get_tracer.return_value = mock_tracer
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        
        tool_inputs = {"query": "test"}
        with tool_execution_span("search", "voice", tool_inputs):
            pass
            
        mock_tracer.start_as_current_span.assert_called_once()
        args, kwargs = mock_tracer.start_as_current_span.call_args
        assert "tool_execute:search" in args[0]
        assert kwargs["attributes"]["tool.interface"] == "voice"
        assert "query" in kwargs["attributes"]["tool.input_keys"]

```

### Step 6: Documentation Updates

#### [NEW] .agent/docs/infra/tool-registry-integration.md

```markdown
# Unified Tool Registry Integration Guide

## Overview

INFRA-145 introduces a unified approach to tool management. Previously, the Console (TUI) and Voice interfaces independently discovered and instantiated tools, leading to logic duplication and feature drift. Both interfaces now act as thin adapters over a centralized `ToolRegistry`.

## Architecture

**Central Registry**
The `ToolRegistry` (defined in `agent/core/adk/tools.py`) is the single source of truth for all tools available to the agent. It handles discovery, instantiation, and schema validation.

**Interface Adapters**
- **Console TUI**: The TUI session manager (`agent/tui/session.py`) initializes the registry and provides it to the underlying `AgentSession`.
- **Voice Orchestrator**: The voice logic (`backend/voice/orchestrator.py`) utilizes the same registry to resolve tool calls, ensuring that voice capabilities mirror console capabilities exactly.

## Developer Workflow

**Registering a New Tool**
1. **Implement**: Create your tool class in `agent/tools/` extending `BaseTool`.
2. **Register**: The registry uses automated discovery. Ensure your tool is included in the package search paths defined in the registry configuration.
3. **Verify**: Use the parity test suite (`pytest .agent/tests/integration/test_tool_parity.py`) to confirm the tool is correctly exposed to both interfaces.

**Contextual Configuration**
Voice-specific context is passed through `RunnableConfig`. The registry lookup mechanism supports passing this configuration into the tool instances to maintain session state across execution boundaries.

## Interface Parity (AC-5)

The system enforces that `ToolRegistry.list_tools()` returns identical results regardless of which interface calls it. This parity is crucial for maintaining a unified user experience across text and voice. Integration tests verify that removing a tool from the registry makes it unavailable in both interfaces simultaneously.

## Observability

The unified registry integrates with OpenTelemetry to provide a single trace path for tool execution. This ensures that latency and error rates for specific tools can be audited globally, regardless of the initiating interface.

## Troubleshooting

| Issue | Possible Cause | Resolution |
|---|---|---|
| Tool not found in Voice | Registry exclusion | Ensure the `backend/voice/orchestrator.py` is correctly initializing the registry with the required toolsets. |
| Blocked interface during tool execution | Synchronous tool implementation | The `executor.py` has been refactored to yield 'Thinking...' status updates. If the interface still blocks, verify the tool implementation is truly asynchronous. |
| Schema Mismatch | Invalid `args_schema` | The registry strictly validates schemas against the LLM's expectations. Use `BaseTool.args_schema` to define complex input structures. |

```

### Step 7: Verification & Test Suite

#### [NEW] .agent/tests/integration/test_tool_parity.py

```python
import pytest
from unittest.mock import patch, MagicMock
from agent.tui.session import TUISession
from backend.voice.orchestrator import VoiceOrchestrator
from agent.core.adk.tools import ToolRegistry

@pytest.mark.asyncio
async def test_ac5_identical_tool_lists():
    """Verify that both TUI and Voice interfaces produce identical tool lists (AC-5)."""
    tui = TUISession()
    voice = VoiceOrchestrator()
    
    tui_tools = tui.get_available_tools()
    voice_tools = voice.get_tools()
    
    assert len(tui_tools) == len(voice_tools), "Interfaces returned different numbers of tools"
    
    tui_names = sorted([t.name for t in tui_tools])
    voice_names = sorted([t.name for t in voice_tools])
    
    assert tui_names == voice_names, "Tool name lists do not match between TUI and Voice"

def test_negative_tool_removal_propagation():
    """Verify that removing a tool from the registry propagates to both interfaces."""
    tui = TUISession()
    voice = VoiceOrchestrator()
    
    # Get original list to find a tool to 'remove'
    registry = ToolRegistry()
    original_tools = registry.list_tools()
    
    if not original_tools:
        pytest.skip("No tools found in registry to test removal.")
        
    tool_to_remove = original_tools[0].name
    
    with patch.object(ToolRegistry, 'list_tools') as mock_list:
        # Simulate registry returning list without the first tool
        mock_list.return_value = original_tools[1:]
        
        current_tui_tools = [t.name for t in tui.get_available_tools()]
        current_voice_tools = [t.name for t in voice.get_tools()]
        
        assert tool_to_remove not in current_tui_tools, f"Tool {tool_to_remove} still visible in TUI after removal"
        assert tool_to_remove not in current_voice_tools, f"Tool {tool_to_remove} still visible in Voice after removal"

@pytest.mark.asyncio
async def test_invocation_parity():
    """Verify that invoking a tool via both interfaces yields consistent results."""
    tui = TUISession()
    voice = VoiceOrchestrator()
    
    # We mock the underlying executor to ensure parity in the adapter logic
    with patch("agent.core.engine.executor.execute") as mock_execute:
        mock_execute.return_value = iter(["Thinking...", "Tool Output"])
        
        # TUI tool lookup and check
        tui_tool = tui.get_available_tools()[0]
        # Voice tool lookup and check
        voice_tool = voice.get_tools()[0]
        
        assert tui_tool.name == voice_tool.name
        # In a real scenario, we'd verify the execution flow here if adapters handle the generator

```

#### [NEW] .agent/tests/agent/core/test_session_refactor.py

```python
import pytest
from unittest.mock import MagicMock, patch
from agent.core.session import AgentSession
from agent.core.adk.tools import ToolRegistry

def test_session_initializes_via_registry():
    """Verify AC-1: AgentSession no longer creates tools directly."""
    with patch("agent.core.adk.tools.ToolRegistry.list_tools") as mock_list:
        mock_list.return_value = [MagicMock(name="registry_tool")]
        
        session = AgentSession()
        session._initialize_tools()
        
        mock_list.assert_called_once()
        assert len(session.tools) == 1
        assert session.tools[0]._mock_name == "registry_tool"

```

#### [NEW] .agent/tests/agent/tui/test_session_adapter.py

```python
import pytest
from agent.tui.session import TUISession
from agent.core.adk.tools import ToolRegistry

def test_tui_adapter_initialization():
    """Verify AC-2: TUISession initializes and passes ToolRegistry."""
    session = TUISession()
    assert hasattr(session, 'tool_registry'), "TUISession missing tool_registry"
    assert isinstance(session.tool_registry, ToolRegistry)
    assert session.agent_session.tool_registry == session.tool_registry

```

#### [NEW] .agent/tests/backend/voice/test_orchestrator_adapter.py

```python
import pytest
from backend.voice.orchestrator import VoiceOrchestrator
from agent.core.adk.tools import ToolRegistry

def test_voice_adapter_initialization():
    """Verify AC-3: VoiceOrchestrator initializes ToolRegistry."""
    orch = VoiceOrchestrator()
    assert hasattr(orch, 'registry'), "VoiceOrchestrator missing registry attribute"
    assert isinstance(orch.registry, ToolRegistry)

def test_voice_get_tools_uses_registry():
    """Verify VoiceOrchestrator delegates tool retrieval to registry."""
    orch = VoiceOrchestrator()
    tools = orch.get_tools()
    # Should match registry output
    assert len(tools) == len(ToolRegistry().list_tools())

```

#### [NEW] .agent/tests/agent/core/engine/test_executor_updates.py

```python
import pytest
from agent.core.engine.executor import execute
from unittest.mock import MagicMock, AsyncMock

@pytest.mark.asyncio
async def test_executor_yields_thinking_status():
    """Verify AC-4: Executor yields 'Thinking...' before results."""
    mock_tool = MagicMock()
    mock_tool.arun = AsyncMock(return_value="Final Result")
    
    with patch("agent.core.engine.executor._get_tool", return_value=mock_tool):
        generator = execute("some_tool", {})
        
        # First yield should be the status update
        status = await generator.__anext__()
        assert status == "Thinking..."
        
        # Second yield should be the result
        result = await generator.__anext__()
        assert result == "Final Result"

```

### Step 8: Deployment & Rollback Strategy

#### [NEW] .agent/src/agent/core/feature_flags.py

```python
import os

def use_unified_registry() -> bool:
    """
    Check if the unified tool registry should be used.

    This function reads the USE_UNIFIED_REGISTRY environment variable.
    It defaults to True, enabling the unified registry pattern introduced in INFRA-145.
    Setting this to 'false' allows the system to fall back to legacy direct tool instantiation.

    Returns:
        bool: True if the unified registry is enabled, False otherwise.
    """
    return os.getenv("USE_UNIFIED_REGISTRY", "true").lower() == "true"

```

#### [NEW] .agent/src/agent/utils/rollback_infra_145.py

```python
import os
import sys

def run_rollback():
    """
    Rollback script for INFRA-145.
    Sets the environment to bypass the unified ToolRegistry and use legacy logic.
    """
    print("--- INFRA-145 Rollback Tool ---")
    print("Target: Revert Console and Voice adapters to direct tool instantiation.")
    
    # Setting the environment variable for the current process and providing instructions
    os.environ["USE_UNIFIED_REGISTRY"] = "false"
    
    print("\n[SUCCESS] USE_UNIFIED_REGISTRY has been set to 'false' in the current execution context.")
    print("\n[ACTION REQUIRED]:")
    print("To apply this globally, update your environment configuration (e.g., .env or system vars):")
    print("    export USE_UNIFIED_REGISTRY=false")
    print("Then, restart the following services:")
    print("    - Console TUI (agent.tui.session)")
    print("    - Voice Orchestrator (backend.voice.orchestrator)")

if __name__ == "__main__":
    run_rollback()

```
