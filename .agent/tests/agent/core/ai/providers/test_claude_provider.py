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

import os
import json
import subprocess
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch, MagicMock

import pytest
import anthropic

from agent.core.ai.providers.claude import (
    ClaudeProvider, 
    load_claude_settings, 
    _apply_settings_env, 
    _run_aws_auth_refresh
)
from agent.core.ai.protocols import AIConfigurationError

@pytest.fixture
def mock_settings_json() -> Dict[str, Any]:
    return {
        "env": {
            "CLAUDE_CODE_USE_BEDROCK": "1",
            "AWS_REGION": "us-east-1",
            "AWS_PROFILE": "test-profile"
        },
        "awsAuthRefresh": "aws sso login --profile test-profile"
    }

def test_load_claude_settings_missing(tmp_path: Path) -> None:
    with patch("pathlib.Path.home", return_value=tmp_path):
        settings = load_claude_settings()
        assert settings == {}

def test_load_claude_settings_valid(tmp_path: Path, mock_settings_json: Dict[str, Any]) -> None:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    settings_file = claude_dir / "settings.json"
    settings_file.write_text(json.dumps(mock_settings_json))
    
    with patch("pathlib.Path.home", return_value=tmp_path):
        settings = load_claude_settings()
        assert settings == mock_settings_json

def test_load_claude_settings_malformed(tmp_path: Path) -> None:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    settings_file = claude_dir / "settings.json"
    settings_file.write_text("{ invalid json }")
    
    with patch("pathlib.Path.home", return_value=tmp_path):
        settings = load_claude_settings()
        assert settings == {}

def test_apply_settings_env() -> None:
    settings: Dict[str, Any] = {"env": {"NEW_VAR": "value", "EXISTING_VAR": "new_value"}}
    with patch.dict(os.environ, {"EXISTING_VAR": "original"}, clear=True):
        _apply_settings_env(settings)
        assert os.environ["NEW_VAR"] == "value"
        assert os.environ["EXISTING_VAR"] == "original"

def test_run_aws_auth_refresh_success() -> None:
    settings: Dict[str, Any] = {"awsAuthRefresh": "aws sso login"}
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        _run_aws_auth_refresh(settings)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["aws", "sso", "login"]
        # Implementation uses shlex.split (no shell=True), which is secure
        assert mock_run.call_args[1].get("shell", False) is False

def test_run_aws_auth_refresh_timeout() -> None:
    settings: Dict[str, Any] = {"awsAuthRefresh": "long_command"}
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["cmd"], 60)):
        # Should not raise exception, just log warning
        _run_aws_auth_refresh(settings)

@patch("agent.core.ai.providers.claude.load_claude_settings")
@patch("agent.core.ai.providers.claude.AnthropicBedrock")
def test_claude_provider_init_bedrock(
    mock_bedrock: MagicMock, mock_load: MagicMock, mock_settings_json: Dict[str, Any]
) -> None:
    mock_load.return_value = mock_settings_json
    # Simulate environment after _apply_settings_env
    env_vars = {"CLAUDE_CODE_USE_BEDROCK": "1", "AWS_REGION": "us-east-1"}
    
    with patch.dict(os.environ, env_vars, clear=True):
        provider = ClaudeProvider(model_id="claude-3-sonnet")
        mock_bedrock.assert_called_once_with(aws_region="us-east-1", aws_profile="test-profile")
        assert provider.model_id == "claude-3-sonnet"

@patch("agent.core.ai.providers.claude.load_claude_settings")
@patch("agent.core.ai.providers.claude.Anthropic")
def test_claude_provider_init_direct(mock_anthropic: MagicMock, mock_load: MagicMock) -> None:
    mock_load.return_value = {}
    env_vars = {"ANTHROPIC_API_KEY": "sk-test-key"}
    
    with patch.dict(os.environ, env_vars, clear=True):
        provider = ClaudeProvider(model_id="claude-3-opus")
        mock_anthropic.assert_called_once_with(api_key="sk-test-key")

def test_claude_provider_init_failure() -> None:
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(AIConfigurationError, match="ANTHROPIC_API_KEY is not set"):
            ClaudeProvider(model_id="test-model")

@patch("agent.core.ai.providers.claude.Anthropic")
def test_claude_provider_generate(mock_anthropic_class: MagicMock) -> None:
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="hello world")]
    )

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "key"}):
        provider = ClaudeProvider(model_id="test-model")
        result = provider.generate("hi")
        assert result == "hello world"
        mock_client.messages.create.assert_called_once()

@patch("agent.core.ai.providers.claude.Anthropic")
def test_claude_provider_stream(mock_anthropic_class: MagicMock) -> None:
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client

    # Create a mock context manager for messages.stream()
    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__enter__ = MagicMock(return_value=mock_stream_ctx)
    mock_stream_ctx.__exit__ = MagicMock(return_value=False)
    mock_stream_ctx.text_stream = iter(["hello", " ", "world"])
    mock_client.messages.stream.return_value = mock_stream_ctx

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "key"}):
        provider = ClaudeProvider(model_id="test-model")
        chunks = list(provider.stream("hi"))
        assert chunks == ["hello", " ", "world"]
        mock_client.messages.stream.assert_called_once()

@patch("agent.core.ai.providers.claude.Anthropic")
def test_claude_provider_generate_reraises_sdk_error(mock_anthropic_class: MagicMock) -> None:
    """SDK exceptions (anthropic.APIError) are re-raised directly, not mapped."""
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client
    mock_client.messages.create.side_effect = anthropic.APIError(
        message="rate limited", request=MagicMock(), body=None,
    )

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "key"}):
        provider = ClaudeProvider(model_id="test-model")
        with pytest.raises(anthropic.APIError, match="rate limited"):
            provider.generate("hi")