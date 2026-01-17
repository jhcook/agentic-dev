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

import sys
from unittest.mock import MagicMock, patch
# Patch Counter to avoid Duplicated Timeseries error during reloads
patch("prometheus_client.Counter").start()

import pytest

# We need to mock import failures or successes before importing agent.core.ai
# Since we can't easily do that for a module already imported, we might need to reload or use patch.dict on sys.modules
from agent.core.ai import AIService


@pytest.fixture
def mock_env_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.delenv("GOOGLE_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

@pytest.fixture
def mock_env_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

@pytest.fixture
def mock_env_none(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

def test_init_openai(mock_env_openai):
    # Mock openai module
    mock_openai = MagicMock()
    with patch.dict(sys.modules, {"openai": mock_openai}):
        ai = AIService()

def test_complete_openai(mock_env_openai):
    mock_openai = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Test response"
    mock_openai.OpenAI.return_value.chat.completions.create.return_value = mock_response
    
    with patch.dict(sys.modules, {"openai": mock_openai}):
        # Force GH check fail to default to OpenAI
        with patch("subprocess.run", side_effect=FileNotFoundError):
            ai = AIService()
            # Double check
            assert ai.provider == "openai"
            response = ai.complete("System", "User")
            assert response == "Test response"

def test_complete_gemini(mock_env_gemini):
    mock_genai = MagicMock()
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Gemini response"
    
    # Structure: Client(api_key=...) -> instance
    mock_genai.Client.return_value = mock_client
    # client.models.generate_content(...) -> response
    # mock streaming response
    mock_chunk = MagicMock()
    mock_chunk.text = "Gemini response"
    mock_client.models.generate_content_stream.return_value = [mock_chunk]
    
    with patch.dict(sys.modules, {"google.genai": mock_genai}):
        # Force GH check fail
        with patch("subprocess.run", side_effect=FileNotFoundError):
            ai = AIService()
            assert ai.provider == "gemini"
            response = ai.complete("System", "User")
            assert response == "Gemini response"
@patch("agent.core.ai.service.os.getenv")
@patch("agent.core.ai.service.subprocess.run")
def test_ai_service_priority(mock_run, mock_getenv):
    """
    Test that GH is prioritized if available, then Gemini, then OpenAI.
    """
    # Handle os.getenv(key, default) signature
    def getenv_side_effect(key, default=None):
        if "API_KEY" in key:
            return "fake_key"
        return default

    # 1. everything available
    mock_getenv.side_effect = getenv_side_effect
    mock_run.return_value.returncode = 0 # gh present
    
    # Reload module to trigger init
    import importlib

    import agent.core.ai.service
    importlib.reload(agent.core.ai.service)
    from agent.core.ai.service import ai_service
    
    assert ai_service.provider == "gh"
    assert "gh" in ai_service.clients
    assert "gemini" in ai_service.clients
    assert "openai" in ai_service.clients

@patch("agent.core.ai.service.os.getenv")
@patch("agent.core.ai.service.subprocess.run")
def test_ai_service_manual_switch(mock_run, mock_getenv):
    """
    Test manual switching logic for retry strategies.
    """
    def getenv_side_effect(key, default=None):
        if "API_KEY" in key:
            return "fake_key"
        return default
        
    mock_getenv.side_effect = getenv_side_effect
    mock_run.return_value.returncode = 0 
    
    import importlib

    import agent.core.ai
    importlib.reload(agent.core.ai)
    from agent.core.ai import ai_service
    
    # 1. Default GH
    assert ai_service.provider == "gh"
    
    # 2. Switch to Gemini
    switched = ai_service.try_switch_provider(ai_service.provider)
    assert switched is True
    assert ai_service.provider == "gemini"
    
    # 3. Switch to OpenAI
    switched = ai_service.try_switch_provider(ai_service.provider)
    assert switched is True
    assert ai_service.provider == "openai"
    
    # 4. No more providers (gh is start, gemini, openai... loop ended)
    switched = ai_service.try_switch_provider(ai_service.provider)
    assert switched is False

@patch("agent.core.ai.service.os.getenv")
@patch("agent.core.ai.service.subprocess.run")
def test_ai_service_exception_propagation(mock_run, mock_getenv):
    """
    Test that complete() raises exception on failure (allowing check.py to catch it).
    """
    mock_getenv.side_effect = lambda k, d=None: "fake_key" if "API_KEY" in k else d
    mock_run.return_value.returncode = 0
    
    import importlib

    import agent.core.ai.service
    importlib.reload(agent.core.ai.service)
    from agent.core.ai.service import ai_service
    
    # Mock _try_complete to fail
    with patch.object(ai_service, "_try_complete", side_effect=Exception("GH Failed")):
        with pytest.raises(Exception) as excinfo:
            ai_service.complete("sys", "user")
        assert "GH Failed" in str(excinfo.value)

@patch("agent.core.ai.service.os.getenv")
@patch("agent.core.ai.service.subprocess.run")
def test_ai_service_provider_override(mock_run, mock_getenv):
    def getenv_side_effect(key, default=None):
        if "API_KEY" in key:
            return "fake_key"
        return default

    mock_getenv.side_effect = getenv_side_effect
    mock_run.return_value.returncode = 0 
    
    import importlib

    import agent.core.ai.service
    importlib.reload(agent.core.ai.service)
    from agent.core.ai.service import ai_service
    
    # Default is GH
    assert ai_service.provider == "gh"
    
    # Override
    ai_service.set_provider("openai")
    assert ai_service.provider == "openai"


@patch("agent.core.ai.service.os.getenv")
@patch("agent.core.ai.service.subprocess.run")
def test_ai_service_api_failure_handling(mock_run, mock_getenv):
    """
    Test that generic API errors (not just rate limits) are raised properly.
    """
    mock_getenv.side_effect = lambda k, d=None: "fake_key" if "API_KEY" in k else d
    mock_run.return_value.returncode = 1 # No GH, force fallback check or just init
    
    import importlib

    import agent.core.ai.service
    importlib.reload(agent.core.ai.service)
    from agent.core.ai.service import ai_service
    
    # Setup OpenAI failure
    ai_service.provider = "openai"
    ai_service.is_forced = True # Bypass Smart Router
    mock_client = MagicMock()
    # Mocking raise of exception
    mock_client.chat.completions.create.side_effect = Exception("API 500 Error")
    ai_service.clients["openai"] = mock_client
    
    with pytest.raises(Exception) as exc:
        ai_service.complete("sys", "user")
    assert "API 500 Error" in str(exc.value)
