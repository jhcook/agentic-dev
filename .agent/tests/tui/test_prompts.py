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

import pytest

import pytest
from unittest.mock import patch, MagicMock

from agent.tui.prompts import (
    build_chat_history,
    _build_clinical_prompt,
    _build_custom_prompt,
    _build_system_prompt,
)


class _MockMessage:
    def __init__(self, role, content):
        self.role = role
        self.content = content


def test_build_chat_history_empty():
    """Test with no history."""
    result = build_chat_history([], "Hello")
    assert result == "User: Hello"


def test_build_chat_history_with_messages():
    """Test formatting with user and assistant history."""
    messages = [
        _MockMessage("user", "What is 2+2?"),
        _MockMessage("assistant", "4"),
    ]
    result = build_chat_history(messages, "Are you sure?")
    
    expected = (
        "User: What is 2+2?\n\n"
        "Assistant: 4\n\n"
        "User: Are you sure?"
    )
    assert result == expected


def test_build_clinical_prompt():
    """Test the original fallback prompt building."""
    header = "TEST HEADER\nLINE 2"
    result = _build_clinical_prompt("test-repo", "/mock/test-repo", header)
    
    assert "You are an expert agentic development assistant embedded in the **test-repo** repository at `/mock/test-repo`." in result
    assert "TEST HEADER" in result
    assert "LINE 2" in result


def test_build_custom_prompt():
    """Test layering of the custom prompt."""
    result = _build_custom_prompt(
        "test-repo",
        "/mock/test-repo",
        "LICENSE HDR",
        "SYSTEM PROMPT MSG",
        "PERSONALITY CONTENT"
    )
    
    assert "SYSTEM PROMPT MSG" in result
    assert "PERSONALITY CONTENT" in result
    assert "You are working in the **test-repo** repository" in result
    assert "LICENSE HDR" in result


@patch("agent.core.config.config")
def test_build_system_prompt_fallback(mock_config):
    """Test fallback to clinical prompt when no personality config exists."""
    mock_config.repo_root.name = "test-repo"
    mock_config.repo_root.__str__.return_value = "/mock/test-repo"
    mock_config.templates_dir.__truediv__.return_value.exists.return_value = False
    mock_config.console.system_prompt = None
    mock_config.console.personality_file = None
    
    # Needs to reset the cache if it were run in a suite
    import agent.tui.prompts as prompts
    prompts._CACHED_SYSTEM_PROMPT = None
    
    result = _build_system_prompt()
    assert "You are an expert agentic development assistant" in result


@patch("agent.tui.prompts.Path")
@patch("agent.core.config.config")
def test_build_system_prompt_custom(mock_config, mock_path_cls):
    """Test loading personality file in _build_system_prompt."""
    mock_config.repo_root.name = "test-repo"
    mock_config.repo_root.__str__.return_value = "/mock/test-repo"
    mock_config.templates_dir.__truediv__.return_value.exists.return_value = False
    mock_config.console.system_prompt = "MY CUSTOM PROMPT"
    mock_config.console.personality_file = "personality.md"
    
    # Path mock setup
    mock_repo_root = MagicMock()
    mock_repo_root.__str__.return_value = "/mock/test-repo"
    
    mock_safe_path = MagicMock()
    mock_safe_path.__str__.return_value = "/mock/test-repo/personality.md"
    mock_safe_path.exists.return_value = True
    mock_safe_path.is_file.return_value = True
    mock_safe_path.read_text.return_value = "PERSONALITY CONTENT loaded from disk"
    
    mock_repo_root.__truediv__.return_value.resolve.return_value = mock_safe_path
    
    # Configure the Path constructor mock to return mock_repo_root when called
    mock_path_cls.return_value.resolve.return_value = mock_repo_root

    import agent.tui.prompts as prompts
    prompts._CACHED_SYSTEM_PROMPT = None
    
    result = prompts._build_system_prompt()
    assert "MY CUSTOM PROMPT" in result
    assert "PERSONALITY CONTENT loaded from disk" in result
    assert "You are working in the **test-repo** repository at `/mock/test-repo`." in result


