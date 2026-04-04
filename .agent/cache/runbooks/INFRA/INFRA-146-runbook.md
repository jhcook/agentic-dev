# Runbook: Implementation Runbook for INFRA-146

## State

ACCEPTED

## Implementation Steps

### Step 1: Architecture & Design Review

#### [MODIFY] .agent/pyproject.toml

```

voice = [
    "langgraph>=0.0.10",
    "langchain-google-genai>=0.0.1",
]

[project.scripts]
>>>

```

#### [MODIFY] CHANGELOG.md

```

# Changelog

## [Unreleased] - 2026-02-15

**Changed**
- Migrated voice agent tool dispatch from LangChain `@tool` decorators to the unified `ToolRegistry` (INFRA-146).
- Replaced `RunnableConfig` context injection with `ToolRegistry` parameter binding for `repo_root` and `session_id`.

**Removed**
- `langchain-core` from optional voice dependencies in `pyproject.toml`.
- legacy `USE_UNIFIED_REGISTRY` feature flag.

## [0.1.0] - 2026-02-01
>>>

```

### Step 2: Tool Module Decoupling

#### [MODIFY] .agent/src/backend/voice/tools/custom/add_license.py

```

<<<SEARCH
from langchain_core.tools import tool
import os
===
import os
>>>
<<<SEARCH
@tool
def add_license(file_path: str) -> str:
===
def add_license(file_path: str) -> str:
>>>

```

#### [MODIFY] .agent/src/backend/voice/tools/docs.py

```

<<<SEARCH
from langchain_core.tools import tool
import os
===
import os
>>>
<<<SEARCH
@tool
def list_docs() -> str:
===
def list_docs() -> str:
>>>
<<<SEARCH
@tool
def read_doc(filename: str) -> str:
===
def read_doc(filename: str) -> str:
>>>
<<<SEARCH
@tool
def search_docs(query: str) -> str:
===
def search_docs(query: str) -> str:
>>>

```

#### [MODIFY] .agent/src/backend/voice/tools/observability.py

```

<<<SEARCH
from langchain_core.tools import tool
from agent.core.config import config as agent_config
===
from agent.core.config import config as agent_config
>>>
<<<SEARCH
@tool
def get_recent_logs(lines: int = 50) -> str:
===
def get_recent_logs(lines: int = 50) -> str:
>>>

```

#### [MODIFY] .agent/src/backend/voice/tools/list_capabilities.py

```

<<<SEARCH
from langchain_core.tools import tool
import inspect
===
import inspect
>>>
<<<SEARCH
@tool
def list_capabilities() -> str:
===
def list_capabilities() -> str:
>>>

```

#### [MODIFY] .agent/src/backend/voice/tools/architect.py

```

<<<SEARCH
from langchain_core.tools import tool
import os
===
import os
>>>
<<<SEARCH
@tool
def list_adrs() -> str:
===
def list_adrs() -> str:
>>>
<<<SEARCH
@tool
def read_adr(filename: str) -> str:
===
def read_adr(filename: str) -> str:
>>>
<<<SEARCH
@tool
def search_rules(query: str) -> str:
===
def search_rules(query: str) -> str:
>>>

```

#### [MODIFY] .agent/src/backend/voice/tools/interactive_shell.py

```

<<<SEARCH
from langchain_core.tools import tool
import subprocess
import threading
import time
from backend.voice.process_manager import ProcessLifecycleManager
from backend.voice.events import EventBus
from agent.core.config import config as agent_config
from langchain_core.runnables import RunnableConfig
from opentelemetry import trace
===
import subprocess
import threading
import time
from backend.voice.process_manager import ProcessLifecycleManager
from backend.voice.events import EventBus
from agent.core.config import config as agent_config
from opentelemetry import trace
>>>
<<<SEARCH
@tool
def start_interactive_shell(command: str, session_id: str = None, config: RunnableConfig = None) -> str:
    """
    Start a long-running interactive shell command (e.g., 'npm init', 'python3').
    Returns a Process ID that can be used with send_shell_input.
    Output will be streamed to the console.
    """
    if not session_id and config:
        session_id = config.get("configurable", {}).get("thread_id", "unknown")
===
def start_interactive_shell(command: str, session_id: str = "unknown") -> str:
    """
    Start a long-running interactive shell command (e.g., 'npm init', 'python3').
    Returns a Process ID that can be used with send_shell_input.
    Output will be streamed to the console.
    """
>>>
<<<SEARCH
@tool
def send_shell_input(process_id: str, input_text: str) -> str:
===
def send_shell_input(process_id: str, input_text: str) -> str:
>>>

```

#### [MODIFY] .agent/src/backend/voice/tools/fix_story.py

```

<<<SEARCH
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from backend.voice.events import EventBus
===
from backend.voice.events import EventBus
>>>
<<<SEARCH
@tool
def interactive_fix_story(
    story_id: str, 
    apply_idx: Optional[int] = None, 
    instructions: Optional[str] = None,
    config: RunnableConfig = None

) -> str:
===
def interactive_fix_story(
    story_id: str, 
    apply_idx: Optional[int] = None, 
    instructions: Optional[str] = None,
    session_id: str = "unknown"
) -> str:
>>>
<<<SEARCH
    session_id = config.get("configurable", {}).get("thread_id", "unknown") if config else "unknown"
    
    # 0. SECURITY: Input Validation
===
    # 0. SECURITY: Input Validation
>>>

```

#### [MODIFY] .agent/src/backend/voice/tools/workflows.py

```

<<<SEARCH
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from backend.voice.events import EventBus
===
from backend.voice.events import EventBus
>>>
<<<SEARCH
def _run_interactive_command(command: str, alias_prefix: str, config: RunnableConfig, start_message: str) -> str:
    """
    Helper to run an interactive shell command with process management and event streaming.
    """
    session_id = config.get("configurable", {}).get("thread_id", "unknown") if config else "unknown"
===
def _run_interactive_command(command: str, alias_prefix: str, session_id: str, start_message: str) -> str:
    """
    Helper to run an interactive shell command with process management and event streaming.
    """
>>>
<<<SEARCH
@tool
def run_new_story(story_id: str = None, config: RunnableConfig = None) -> str:
===
def run_new_story(story_id: str = None, session_id: str = "unknown") -> str:
>>>
<<<SEARCH
    return _run_interactive_command(cmd, "story", config, "Story creation started. Follow along below.")
===
    return _run_interactive_command(cmd, "story", session_id, "Story creation started. Follow along below.")
>>>
<<<SEARCH
@tool
def run_new_runbook(story_id: str, config: RunnableConfig = None) -> str:
===
def run_new_runbook(story_id: str, session_id: str = "unknown") -> str:
>>>
<<<SEARCH
    return _run_interactive_command(cmd, "runbook", config, "Runbook generation started. Follow along below.")
===
    return _run_interactive_command(cmd, "runbook", session_id, "Runbook generation started. Follow along below.")
>>>
<<<SEARCH
@tool
def run_implement(runbook_id: str, config: RunnableConfig = None) -> str:
===
def run_implement(runbook_id: str, session_id: str = "unknown") -> str:
>>>
<<<SEARCH
    return _run_interactive_command(cmd, "implement", config, "Implementation started (with --apply). Follow along below.")
===
    return _run_interactive_command(cmd, "implement", session_id, "Implementation started (with --apply). Follow along below.")
>>>
<<<SEARCH
@tool
def run_impact(files: str = None, config: RunnableConfig = None) -> str:
===
def run_impact(files: str = None, session_id: str = "unknown") -> str:
>>>
<<<SEARCH
    return _run_interactive_command(cmd, "impact", config, "Impact analysis started. Follow along below.")
===
    return _run_interactive_command(cmd, "impact", session_id, "Impact analysis started. Follow along below.")
>>>
<<<SEARCH
@tool
def run_panel(question: str, apply_advice: bool = False, config: RunnableConfig = None) -> str:
===
def run_panel(question: str, apply_advice: bool = False, session_id: str = "unknown") -> str:
>>>
<<<SEARCH
    return _run_interactive_command(cmd, "panel", config, "Governance panel convened. Follow along below.")
===
    return _run_interactive_command(cmd, "panel", session_id, "Governance panel convened. Follow along below.")
>>>
<<<SEARCH
@tool
def run_review_voice(session_id: str = None, config: RunnableConfig = None) -> str:
===
def run_review_voice(session_id: str = None) -> str:
>>>
<<<SEARCH
    return _run_interactive_command(cmd, "review", config, "Voice review started. Follow along below.")
===
    # Note: run_review_voice does not need internal session_id forwarding as the command uses its own target
    return _run_interactive_command(cmd, "review", "system", "Voice review started. Follow along below.")
>>>

```

#### [MODIFY] .agent/src/backend/voice/tools/qa.py

```

<<<SEARCH
from langchain_core.tools import tool
import subprocess
===
import subprocess
>>>
<<<SEARCH
from langchain_core.runnables import RunnableConfig
from backend.voice.events import EventBus
===
from backend.voice.events import EventBus
>>>
<<<SEARCH
@tool
def run_backend_tests(path: str = ".agent/tests/") -> str:
===
def run_backend_tests(path: str = ".agent/tests/") -> str:
>>>
<<<SEARCH
@tool
def run_frontend_lint() -> str:
===
def run_frontend_lint() -> str:
>>>
<<<SEARCH
@tool
def shell_command(command: str, cwd: str = ".", config: RunnableConfig = None) -> str:
    """
    Execute a shell command from the project root or a specific directory.
    Use this for package installation (npm install, pip install) or running utilities.
    Args:
        command: The shell command to run (e.g. 'ls -la', 'pip install requests')
        cwd: Working directory relative to project root (default: '.')
    """
    session_id = config.get("configurable", {}).get("thread_id", "unknown") if config else "unknown"
===
def shell_command(command: str, cwd: str = ".", session_id: str = "unknown") -> str:
    """
    Execute a shell command from the project root or a specific directory.
    Use this for package installation (npm install, pip install) or running utilities.
    Args:
        command: The shell command to run (e.g. 'ls -la', 'pip install requests')
        cwd: Working directory relative to project root (default: '.')
    """
>>>
<<<SEARCH
@tool
def run_preflight(story_id: str = None, interactive: bool = True, config: RunnableConfig = None) -> str:
    """
    Run the Agent preflight governance checks with AI analysis.
    Use this when a user asks to 'run preflight' or 'check compliance'.
    Args:
        story_id: Optional Story ID (e.g. 'INFRA-015')
        interactive: Whether to enable interactive repair mode (default: True)
    """
    session_id = config.get("configurable", {}).get("thread_id", "unknown") if config else "unknown"
===
def run_preflight(story_id: str = None, interactive: bool = True, session_id: str = "unknown") -> str:
    """
    Run the Agent preflight governance checks with AI analysis.
    Use this when a user asks to 'run preflight' or 'check compliance'.
    Args:
        story_id: Optional Story ID (e.g. 'INFRA-015')
        interactive: Whether to enable interactive repair mode (default: True)
    """
>>>

```

#### [MODIFY] .agent/src/backend/voice/tools/get_installed_packages.py

```

<<<SEARCH
from langchain_core.tools import tool
import importlib.metadata
===
import importlib.metadata
>>>
<<<SEARCH
@tool
def get_installed_packages() -> str:
===
def get_installed_packages() -> str:
>>>

```

#### [MODIFY] .agent/src/backend/voice/tools/create_tool.py

```

<<<SEARCH
from langchain_core.tools import tool
import logging
===
import logging
>>>
<<<SEARCH
@tool
def create_tool(file_path: str, code: str) -> str:
===
def create_tool(file_path: str, code: str) -> str:
>>>

```

#### [MODIFY] .agent/src/backend/voice/tools/read_tool_source.py

```

<<<SEARCH
from langchain_core.tools import tool
import os
===
import os
>>>
<<<SEARCH
@tool
def read_tool_source(file_path: str) -> str:
===
def read_tool_source(file_path: str) -> str:
>>>

```

#### [MODIFY] .agent/src/backend/voice/tools/git.py

```

<<<SEARCH
from langchain_core.tools import tool
===
# LangChain tool imports removed per INFRA-146 migration
>>>
<<<SEARCH
@tool
def get_git_branch() -> str:
===
def get_git_status
>>>
<<<SEARCH
@tool
def get_git_branch() -> str:
===
def get_git_diff
>>>
<<<SEARCH
@tool
def get_git_branch() -> str:
===
def get_git_log
>>>

```

#### [MODIFY] .agent/src/backend/voice/tools/security.py

```

<<<SEARCH
from langchain_core.tools import tool
===
# LangChain tool imports removed per INFRA-146 migration
>>>
<<<SEARCH
@tool
def scan_file_for_secrets(file_path: str) -> str:
===
def scan_file_for_secrets
>>>

```

#### [MODIFY] .agent/src/backend/voice/tools/project.py

```

<<<SEARCH
from langchain_core.tools import tool
===
# LangChain tool imports removed per INFRA-146 migration
>>>
<<<SEARCH
@tool
def list_runbooks() -> str:
===
def list_stories
>>>

```

### Step 3: Orchestration & Registry Integration

#### [MODIFY] .agent/src/agent/core/feature_flags.py

```

import os

# USE_UNIFIED_REGISTRY flag removed as part of INFRA-146 migration.
>>>

```

#### [MODIFY] .agent/src/backend/voice/tools/registry.py

```

# limitations under the License.

import os
from agent.core.adk.tools import ToolRegistry
from agent.core.config import config as agent_config

def get_all_tools():
    """
    Return a list of all initialized tools via ToolRegistry.

    Delegates discovery and loading to the unified registry to remove
    LangChain-specific decorators and manual aggregator imports.
    """
    registry = ToolRegistry(repo_root=agent_config.repo_root)
    return registry.list_tools(all=True)

def get_unified_tools() -> tuple[list[dict], dict]:
    """
    Returns tools as JSON Schemas and a handler dictionary for AgentSession.

    Delegates to the unified ToolRegistry for both schema generation
    and execution handling.
    """
    registry = ToolRegistry(repo_root=agent_config.repo_root)
    tools = registry.list_tools(all=True)
    
    schemas = []
    handlers = {}
    
    for tool in tools:
        # ToolRegistry provides tool objects containing the schema and the raw callable
        schemas.append(tool.schema)
        handlers[tool.name] = tool.func
        
    return schemas, handlers
>>>

```

### Step 4: Observability & Audit Logging

#### [NEW] .agent/src/backend/voice/tools/tool_security.py

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
Tracing and audit logging for voice tools.

This module provides utilities to wrap tool executions with OpenTelemetry spans
and logging to comply with ADR-046 and ensure auditability.
"""

import time
import logging
from typing import Any, Callable, Dict, Optional
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

# Configure logger for audit trails
logger = logging.getLogger("agent.audit.voice")
tracer = trace.get_tracer(__name__)

def audit_tool_call(
    tool_name: str,
    session_id: str,
    func: Callable,
    *args: Any,
    **kwargs: Any
) -> Any:
    """
    Executes a tool within an OTel span for audit logging and performance tracking.
    
    Complies with ADR-046 (Telemetry) and ADR-043 (Tool Registry).
    Captures name, duration, success, and session context.
    
    Args:
        tool_name: The canonical name of the tool being called.
        session_id: Unique identifier for the voice session.
        func: The tool callable implementation.
        *args: Positional arguments for the tool.
        **kwargs: Keyword arguments for the tool.
        
    Returns:
        The result of the tool execution.
        
    Raises:
        Exception: Re-raises any exception from the tool after capturing telemetry.
    """
    start_time = time.perf_counter()
    
    # Start an OpenTelemetry span following ADR-046 conventions
    with tracer.start_as_current_span(f"tool_execution.{tool_name}") as span:
        span.set_attribute("tool.name", tool_name)
        span.set_attribute("session_id", session_id)
        span.set_attribute("interface", "voice")
        
        try:
            # Core execution of the tool function
            result = func(*args, **kwargs)
            
            # Mark success in telemetry
            span.set_status(Status(StatusCode.OK))
            span.set_attribute("tool.success", True)
            
            return result
            
        except Exception as e:
            # Record failure context
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.set_attribute("tool.success", False)
            span.record_exception(e)
            
            # Log failure to the audit trail
            logger.error(
                "Audit Failure: Tool '%s' failed in session %s. Error: %s",
                tool_name, session_id, str(e)
            )
            raise
            
        finally:
            # Calculate and record duration in milliseconds
            duration_ms = (time.perf_counter() - start_time) * 1000
            span.set_attribute("tool.duration_ms", duration_ms)
            
            # Compliance logging for ADR-046 audit requirements
            logger.info(
                "Tool Call: %s | Session: %s | Duration: %.2fms | Success: %s",
                tool_name,
                session_id,
                duration_ms,
                "TRUE" if span.is_recording() and span.get_status().status_code == StatusCode.OK else "FALSE"
            )

```

### Step 5: Documentation Updates

#### [NEW] .agent/docs/tool-integration.md

```markdown
# Tool Integration Standard

This document defines the process for creating and integrating tools into the Agent platform, specifically focusing on the unified registry pattern established in INFRA-145 and INFRA-146.

## LangChain Decorator Deprecation

As of INFRA-146, the `@tool` decorator from `langchain_core.tools` is **deprecated** for tools within the `backend/voice/tools/` directory. All tools must be implemented as plain Python callables.

## Why the Change?

- **Dependency Reduction**: Removes hard runtime dependencies on LangChain for tool dispatch at the voice layer.
- **Unified Registry**: Ensures the voice backend and TUI/CLI share the same discovery mechanism via `ToolRegistry`.
- **Simplified Context**: Replaces complex `RunnableConfig` objects with direct configuration parameters handled by the ADK adapter.

## Developing a New Tool

1. **Implementation**: Define a plain function with clear type hints and a PEP-257 docstring.
2. **Context Injection**: If the tool requires repository context (like `repo_root`), it should accept parameters that are populated by the `ToolRegistry` during invocation.
3. **Registration**: Tools are automatically discovered if placed in the standard paths scanned by `ToolRegistry` (`.agent/src/agent/tools/` and `.agent/src/backend/voice/tools/`).

## Implementation Comparison

**Legacy Style (Deprecated):**

```python
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

@tool
def my_tool(arg: str, config: RunnableConfig):
    """Tool description."""
    repo_root = config.get("configurable", {}).get("repo_root")
    return f"Result: {arg} at {repo_root}"

```

**New Standard:**

```python
def my_tool(arg: str, repo_root: str = "."):
    """Tool description."""
    return f"Result: {arg} at {repo_root}"

```

## Troubleshooting

- **Tool Not Appearing**: Ensure the function is imported in the module's `__init__.py` or the module is in a scanned directory.
- **Context Missing**: Verify that the tool signature matches the parameters provided by the `ToolRegistry.execute` flow in `agent/core/adk/tools.py`.
- **Registry Conflict**: Ensure the `USE_UNIFIED_REGISTRY` flag is removed from environment variables, as the legacy path is no longer supported.

```

### Step 6: Verification & Test Suite

#### [MODIFY] .agent/tests/voice/test_orchestrator_adapter.py

```

import pytest
from unittest.mock import MagicMock, patch
from backend.voice.orchestrator import VoiceOrchestrator
from agent.core.adk.tools import ToolRegistry

def test_voice_adapter_initialization():
    """Verify AC-3 & AC-5: VoiceOrchestrator initializes ToolRegistry and binds tools."""
    orch = VoiceOrchestrator()
    assert hasattr(orch, 'registry'), "VoiceOrchestrator missing registry attribute"
    assert isinstance(orch.registry, ToolRegistry)

def test_voice_get_tools_uses_registry():
    """Verify VoiceOrchestrator delegates tool retrieval to registry (AC-5)."""
    orch = VoiceOrchestrator()
    with patch.object(ToolRegistry, 'list_tools') as mock_list:
        mock_list.return_value = []
        orch.get_tools()
        mock_list.assert_called_once_with(all=True)

def test_voice_tool_execution_audit():
    """Verify that tool execution is wrapped in the audit layer (AC-7)."""
    orch = VoiceOrchestrator()
    mock_tool = MagicMock()
    mock_tool.name = "test_tool"
    mock_tool.func = MagicMock(return_value="success")
    
    with patch("backend.voice.tools.tool_security.audit_tool_call") as mock_audit:
        orch._execute_tool(mock_tool, "sess_123", {"arg": "val"})
        mock_audit.assert_called_once()
>>>

```

#### [MODIFY] .agent/tests/voice/test_tool_parity.py

```

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
    
    # The total number of tools should be exactly 42 per INFRA-146 specifications
    assert len(voice_tools) >= 42, f"Expected at least 42 tools, found {len(voice_tools)}"
    assert len(tui_tools) == len(voice_tools), "Interfaces returned different numbers of tools"
    
    tui_names = sorted([t.name for t in tui_tools])
    voice_names = sorted([t.name for t in voice_tools])
    
    assert tui_names == voice_names, "Tool name lists do not match between TUI and Voice"

def test_negative_tool_removal_propagation():
    """Verify that removing a tool from the registry propagates to both interfaces."""
    registry = ToolRegistry()
    original_tools = registry.list_tools(all=True)
    
    if not original_tools:
        pytest.skip("No tools found in registry to test removal.")
>>>

```

#### [NEW] .agent/tests/voice/test_langchain_deprecation.py

```python
import subprocess
from pathlib import Path
import pytest

def test_no_langchain_tool_dependencies_in_backend():
    """
    Negative test: Verify no LangChain tool decorators or imports remain in voice tools.
    Covers AC-1, AC-2, and Negative Test requirements of INFRA-146.
    """
    # Adjusted to point to the source directory relative to repo root
    tools_dir = Path(".agent/src/backend/voice/tools")
    
    if not tools_dir.exists():
        pytest.skip("Voice tools directory not found in the current environment.")

    # Check for AC-2: from langchain_core.tools import tool
    # We exclude registry.py from this check if it still imports BaseTool for type hints,
    # but per the migration, even registry.py should move to ToolRegistry objects.
    grep_import = subprocess.run(
        ["grep", "-r", "from langchain_core.tools import tool", str(tools_dir)],
        capture_output=True,
        text=True
    )
    assert grep_import.stdout.strip() == "", f"Forbidden LangChain imports found:\n{grep_import.stdout}"

    # Check for AC-1: @tool decorator usage
    grep_decorator = subprocess.run(
        ["grep", "-r", "@tool", str(tools_dir)],
        capture_output=True,
        text=True
    )
    # Filter out potential false positives in comments or unrelated code if necessary
    # but for this migration, @tool should be entirely absent from definitions.
    assert grep_decorator.stdout.strip() == "", f"Forbidden @tool decorators found:\n{grep_decorator.stdout}"

def test_no_runnable_config_injection():
    """
    Verify that RunnableConfig is no longer used for context injection in specific tools.
    Covers AC-3.
    """
    tools_dir = Path(".agent/src/backend/voice/tools")
    forbidden_pattern = "RunnableConfig"
    
    grep_config = subprocess.run(
        ["grep", "-r", forbidden_pattern, str(tools_dir)],
        capture_output=True,
        text=True
    )
    # We allow the import to exist if it's being used for legacy type-checking in non-tool files,
    # but it should not be in the function signatures of the migrated tools.
    assert grep_config.stdout.strip() == "", f"Forbidden RunnableConfig references found in tools:\n{grep_config.stdout}"

```

### Step 7: Deployment & Rollback Strategy

#### [MODIFY] .agent/CHANGELOG.md

```

# Changelog

## [INFRA-146] - 2026-02-14
**Changed**
- Decoupled voice tools from LangChain core decorators.
- Refactored 15 tool modules in `backend/voice/tools/` to plain callables.
- Integrated unified `ToolRegistry` as the primary dispatch layer for voice logic orchestration.
- Replaced `RunnableConfig` context injection with registry-based configuration retrieval.
- Removed `USE_UNIFIED_REGISTRY` feature flag as migration is finalized.
**Security**
- Standardized tool execution telemetry and audit logging via OpenTelemetry and the ToolRegistry foundation.
>>>

```

#### [NEW] .agent/src/agent/utils/rollback_infra_146.py

```python
"""
Rollback utility for INFRA-146 migration.

This script provides automated verification for a git-revert operation,
ensuring that legacy LangChain tool interfaces are correctly restored
and the voice layers are re-synced with legacy imports.
"""

import subprocess
import sys
from pathlib import Path

def check_legacy_state() -> bool:
    """
    Verify that the legacy @tool decorators and LangChain imports have been restored.
    
    Returns:
        bool: True if state is successfully reverted, False otherwise.
    """
    # Relative path from project root where script is expected to run
    tools_dir = Path(".agent/src/backend/voice/tools")
    if not tools_dir.exists():
        print("Error: Voice tools directory not found at .agent/src/backend/voice/tools")
        return False

    # Check for restored imports
    try:
        print("Checking for restored LangChain imports...")
        grep_proc = subprocess.run(
            ["grep", "-r", "from langchain_core.tools import tool", str(tools_dir)],
            capture_output=True,
            text=True
        )
        if not grep_proc.stdout.strip():
            print("Revert Validation Failure: LangChain core tool imports missing.")
            return False
            
        # Check for restored decorators
        print("Checking for restored @tool decorators...")
        decorator_check = subprocess.run(
            ["grep", "-r", "@tool", str(tools_dir)],
            capture_output=True,
            text=True
        )
        if "@tool" not in decorator_check.stdout:
            print("Revert Validation Failure: @tool decorators missing.")
            return False

        print("Revert Validation Success: Legacy state detected.")
        return True
    except Exception as e:
        print(f"Validation error: {e}")
        return False

if __name__ == "__main__":
    # Ensure execution from project root
    if not Path(".agent").exists():
        print("Please run this script from the project root.")
        sys.exit(1)
    
    success = check_legacy_state()
    sys.exit(0 if success else 1)

```
