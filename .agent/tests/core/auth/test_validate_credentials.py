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
import pytest
from unittest.mock import patch, MagicMock
from agent.core.auth.credentials import validate_credentials
from agent.core.auth.errors import MissingCredentialsError

@pytest.fixture
def mock_secret_manager():
    with patch("agent.core.auth.credentials.get_secret_manager") as mock:
        manager = MagicMock()
        mock.return_value = manager
        yield manager

@pytest.fixture(autouse=True)
def mock_ai_provider():
    """Ensure ai_service.provider is None so LLM_PROVIDER takes effect."""
    with patch("agent.core.ai.ai_service") as mock_ai:
        mock_ai.provider = None
        yield mock_ai

@pytest.fixture
def clear_env():
    """Clear relevant env vars before each test."""
    with patch.dict(os.environ, {}, clear=True):
        yield

def test_validate_credentials_has_env_var(clear_env, mock_secret_manager):
    """Should pass if OPENAI_API_KEY is in env."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}), \
         patch("agent.core.auth.credentials.LLM_PROVIDER", "openai"):
        validate_credentials()  # Should not raise

def test_validate_credentials_has_secret_store(clear_env, mock_secret_manager):
    """Should pass if secret store has the key."""
    # Env empty, secret store returns value for openai
    mock_secret_manager.is_unlocked.return_value = True
    mock_secret_manager.get_secret.side_effect = lambda s, k: "secret-value" if s=="openai" and k=="api_key" else None
    
    with patch("agent.core.auth.credentials.LLM_PROVIDER", "openai"):
        validate_credentials() # Should not raise

def test_validate_credentials_missing_both(clear_env, mock_secret_manager):
    """Should raise error if missing in both."""
    mock_secret_manager.is_unlocked.return_value = True
    mock_secret_manager.get_secret.return_value = None
    
    with patch("agent.core.auth.credentials.LLM_PROVIDER", "openai"):
        with pytest.raises(MissingCredentialsError) as exc:
            validate_credentials()
    
        assert "OPENAI_API_KEY" in str(exc.value)

def test_validate_credentials_secret_manager_locked(clear_env, mock_secret_manager):
    """
    If secret manager is locked or returns None, and env is empty, fails.
    """
    mock_secret_manager.is_unlocked.return_value = True
    mock_secret_manager.get_secret.return_value = None
    
    with patch("agent.core.auth.credentials.LLM_PROVIDER", "openai"):
        with pytest.raises(MissingCredentialsError):
            validate_credentials()

def test_dynamic_provider_switching(clear_env, mock_secret_manager):
    """Test that it checks correct keys when LLM_PROVIDER changes."""
    mock_secret_manager.is_unlocked.return_value = True
    # 1. Anthropic
    with patch("agent.core.auth.credentials.LLM_PROVIDER", "anthropic"):
        # Missing check
        mock_secret_manager.get_secret.return_value = None
        with pytest.raises(MissingCredentialsError) as exc:
            validate_credentials()
        assert "ANTHROPIC_API_KEY" in str(exc.value)
        
        # Present check (Env)
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
            validate_credentials() # Should pass

    # 2. Gemini
    with patch("agent.core.auth.credentials.LLM_PROVIDER", "gemini"):
        # Env check (GEMINI_API_KEY — canonical name)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "AIza..."}):
            validate_credentials() # Should pass
