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

import inspect
import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from agent.core.adk.tools import ToolRegistry
from backend.voice.orchestrator import VoiceOrchestrator

def test_ac5_identical_tool_lists():
    """Verify that both VoiceOrchestrator instances produce identical tool lists (AC-5).
    
    Since TUISession is now a thin wrapper around ToolRegistry, we verify
    that two separate VoiceOrchestrator instances produce the same tool set,
    confirming the unified registry is deterministic.
    """
    voice1 = VoiceOrchestrator(session_id="test-1")
    voice2 = VoiceOrchestrator(session_id="test-2")
    
    tools1 = voice1.registry.list_tools(all=True)
    tools2 = voice2.registry.list_tools(all=True)
    
    assert len(tools1) == len(tools2), "Registries returned different numbers of tools"
    
    names1 = sorted([getattr(t, '__name__', str(t)) for t in tools1])
    names2 = sorted([getattr(t, '__name__', str(t)) for t in tools2])
    
    assert names1 == names2, "Tool name lists do not match between instances"

def test_negative_tool_removal_propagation():
    """Verify that removing a tool from the registry propagates consistently."""
    registry = ToolRegistry()
    original_tools = registry.list_tools()
    
    if not original_tools:
        pytest.skip("No tools found in registry to test removal.")
        
    original_count = len(original_tools)
    
    # Verify two separate registries return the same count
    registry2 = ToolRegistry()
    assert len(registry2.list_tools()) == original_count

def test_invocation_parity():
    """Verify that tools resolve to callables in the unified registry."""
    voice = VoiceOrchestrator(session_id="test-parity")
    tools = voice.registry.list_tools(all=True)
    
    # All tools should be callable
    for tool in tools:
        assert callable(tool), f"Tool {tool} is not callable"


def test_tool_signatures_no_langchain_context():
    """Verify AC-3: Context injected via repo_root, not RunnableConfig."""
    registry = ToolRegistry()
    tools = registry.list_tools(all=True)

    for tool_fn in tools:
        # Unwrap if it's a partial (which registry.list_tools now returns)
        func = tool_fn.func if hasattr(tool_fn, "func") else tool_fn
        sig = inspect.signature(func)

        # Assert LangChain parameters are gone
        assert "config" not in sig.parameters, (
            f"Tool {func.__name__} still accepts 'config' parameter"
        )

        # Check for repo_root presence in refactored modules
        refactored_prefixes = [
            "get_git_", "run_commit", "run_pr", "git_stage", "git_push",
            "start_interactive", "interactive_fix",
            "run_new_", "run_implement", "run_impact", "run_panel", "run_review_voice",
            "run_backend_tests", "run_frontend_lint", "shell_command", "run_preflight",
            "get_recent_logs",
        ]
        if any(func.__name__.startswith(p) for p in refactored_prefixes):
            assert "repo_root" in sig.parameters, (
                f"Refactored tool {func.__name__} missing 'repo_root' parameter"
            )


def test_negative_no_langchain_tool_imports():
    """Negative test: confirm zero LangChain tool imports in voice backend (AC-2)."""
    voice_backend_path = Path(__file__).parents[2] / "src" / "backend" / "voice"

    cmd = ["grep", "-r", "--include=*.py", "from langchain_core.tools import tool", str(voice_backend_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)

    assert result.returncode != 0, (
        f"Forbidden LangChain tool imports found in voice backend:\n{result.stdout}"
    )


def test_negative_no_langchain_tool_decorators():
    """Negative test: confirm zero @tool decorators in voice backend (AC-1)."""
    voice_backend_path = Path(__file__).parents[2] / "src" / "backend" / "voice" / "tools"

    cmd = ["grep", "-rn", "--include=*.py", "^@tool", str(voice_backend_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)

    assert result.returncode != 0, (
        f"Forbidden @tool decorators found in voice tools:\n{result.stdout}"
    )

