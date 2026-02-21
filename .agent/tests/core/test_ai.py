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


from agent.core.secrets import get_secret_manager

@pytest.fixture(autouse=True)
def mock_secret_manager():
    """Ensure tests don't access real secrets."""
    with patch("agent.core.ai.service.get_secret") as mock_get:
        # We want get_secret to fall back to env vars, so we can't just return None.
        # But get_secret implementation calls get_secret_manager.
        # It's better to patch get_secret_manager to return a locked manager.
        pass

    with patch("agent.core.secrets.get_secret_manager") as mock_mgr:
        manager = MagicMock()
        manager.is_initialized.return_value = False # Force fallback to env
        manager.is_unlocked.return_value = False
        mock_mgr.return_value = manager
        yield mock_mgr

@pytest.fixture
def mock_env_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

@pytest.fixture
def mock_env_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

@pytest.fixture
def mock_env_none(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


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
        # Mock config to prevent loading real agent.yaml
        with patch("agent.core.config.config.load_yaml", return_value={}):
            # Force GH check fail to default to OpenAI
            with patch("subprocess.run", side_effect=FileNotFoundError):
                ai = AIService()
                ai.reload()
                ai._initialized = True
                # Double check
                assert ai.provider == "openai"
                response = ai.complete("System", "User")
                assert response == "Test response"

@pytest.mark.skip(reason="Mocking issues with google.genai Pydantic validation")
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
        # Force patch in case it's disregarded by existing imports
        old_module = sys.modules.get("google.genai")
        sys.modules["google.genai"] = mock_genai
        
        try:
            # Define dummy classes to avoid MagicMock Pydantic issues
            class Dummy:
                def __init__(self, **kwargs):
                    self.__dict__.update(kwargs)
                    # Ensure common attributes exist to prevent errors
                    self.base_url = kwargs.get("base_url")
                    self.tools = kwargs.get("tools")
                    self.timeout = kwargs.get("timeout")
                
                def model_copy(self, **kwargs):
                    return self
                    
                def __getattr__(self, name):
                    return None
                
            mock_genai.types.HttpOptions = Dummy
            mock_genai.types.AutomaticFunctionCallingConfig = Dummy
            mock_genai.types.GenerateContentConfig = Dummy
            
            # Force GH check fail
            with patch("subprocess.run", side_effect=FileNotFoundError):
                ai = AIService()
                assert ai.provider == "gemini"
                response = ai.complete("System", "User")
                assert response == "Gemini response"
        finally:
            if old_module:
                 sys.modules["google.genai"] = old_module
            else:
                 sys.modules.pop("google.genai", None)
        

@patch("agent.core.ai.service.subprocess.run")
def test_ai_service_priority(mock_run, monkeypatch):
    """
    Test that GH is prioritized if available, then Gemini, then OpenAI.
    """
    # Set fake keys to ensure providers are eligible
    monkeypatch.setenv("OPENAI_API_KEY", "fake_key")
    monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake_key")

    # Mock subprocess.run return values for GH CLI checks
    # 1. gh --version (success)
    # 2. gh extension list (contains gh-models)
    mock_ret = MagicMock()
    mock_ret.returncode = 0
    mock_ret.stdout = "gh-models"
    mock_run.return_value = mock_ret

    # Mock AI libraries
    mock_genai = MagicMock()
    mock_openai = MagicMock()
    mock_anthropic = MagicMock()
    
    with patch.dict(sys.modules, {
        "google": MagicMock(),
        "google.genai": mock_genai,
        "openai": mock_openai,
        "anthropic": mock_anthropic
    }):
        # Mock config to ignore local agent.yaml which might set provider
        with patch("agent.core.config.config.load_yaml", return_value={}):
            from agent.core.ai.service import AIService
            ai_service = AIService()
            ai_service.reload()
            ai_service._initialized = True
            
            assert ai_service.provider == "gh"
            assert "gh" in ai_service.clients
            assert "gemini" in ai_service.clients
            assert "openai" in ai_service.clients

@pytest.mark.skip(reason="Flaky in CI environment despite mocking")
@patch("agent.core.ai.service.subprocess.run")
def test_ai_service_manual_switch(mock_run, monkeypatch):
    """
    Test manual switching logic for retry strategies.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "fake_key")
    monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
    
    mock_ret = MagicMock()
    mock_ret.returncode = 0
    mock_ret.stdout = "gh-models"
    mock_run.return_value = mock_ret 
    
    # Mock AI libraries
    mock_genai = MagicMock()
    mock_openai = MagicMock()
    mock_anthropic = MagicMock()

    with patch.dict(sys.modules, {
        "google": MagicMock(),
        "google.genai": mock_genai,
        "openai": mock_openai,
        "anthropic": mock_anthropic
    }):
        with patch("agent.core.config.config.load_yaml", return_value={}):
            from agent.core.ai.service import AIService
            ai_service = AIService()
            ai_service.reload()
            ai_service._initialized = True
            
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

@patch("agent.core.ai.service.subprocess.run")
def test_ai_service_exception_propagation(mock_run, monkeypatch):
    """
    Test that complete() raises exception on failure (allowing check.py to catch it).
    """
    monkeypatch.setenv("OPENAI_API_KEY", "fake_key")
    
    mock_ret = MagicMock()
    mock_ret.returncode = 0
    mock_ret.stdout = "gh-models"
    mock_run.return_value = mock_ret
    
    from agent.core.ai.service import AIService
    ai_service = AIService()
    ai_service.reload()
    ai_service._initialized = True
    
    # Mock _try_complete to fail
    with patch.object(ai_service, "_try_complete", side_effect=Exception("GH Failed")):
        with pytest.raises(Exception) as excinfo:
            ai_service.complete("System prompt", "User prompt")
        assert "GH Failed" in str(excinfo.value)

@patch("agent.core.ai.service.subprocess.run")
def test_ai_service_provider_override(mock_run, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake_key")
    
    mock_ret = MagicMock()
    mock_ret.returncode = 0
    mock_ret.stdout = "gh-models"
    mock_run.return_value = mock_ret 
    
    with patch.dict(sys.modules, {
        "google": MagicMock(),
        "google.genai": MagicMock(),
        "openai": MagicMock(),
        "anthropic": MagicMock()
    }):
        with patch("agent.core.config.config.load_yaml", return_value={}):
            from agent.core.ai.service import AIService
            ai_service = AIService()
            ai_service.reload()
            ai_service._initialized = True
            
            # Default is GH
            assert ai_service.provider == "gh"
        
        # Override
        ai_service.set_provider("openai")
        assert ai_service.provider == "openai"


@patch("agent.core.ai.service.subprocess.run")
def test_ai_service_api_failure_handling(mock_run, monkeypatch):
    """
    Test that generic API errors (not just rate limits) are raised properly.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "fake_key")
    mock_run.return_value.returncode = 1 # No GH, force fallback check or just init
    
    with patch.dict(sys.modules, {
        "google": MagicMock(),
        "google.genai": MagicMock(),
        "openai": MagicMock(),
        "anthropic": MagicMock()
    }):
        with patch("agent.core.config.config.load_yaml", return_value={}):
            from agent.core.ai.service import AIService
            ai_service = AIService()
            ai_service.reload()
            ai_service._initialized = True
            
            # Ensure ONLY openai (and gh) are present to prevent fallback to anthropic/gemini
            keys_to_remove = [k for k in ai_service.clients if k not in ["openai", "gh"]]
            for k in keys_to_remove:
                ai_service.clients.pop(k, None)
        
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
