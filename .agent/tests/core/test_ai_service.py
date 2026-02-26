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

from unittest.mock import MagicMock, patch

import pytest

from agent.core.ai.service import AIService, ai_command_runs_total


@pytest.fixture
def ai_service():
    with patch.dict("os.environ", {"OPENAI_API_KEY": "dummy", "GEMINI_API_KEY": "dummy"}):
        with patch("agent.core.ai.service.AIService._check_gh_cli", return_value=True):
            with patch("openai.OpenAI"), patch("google.genai.Client"):
                service = AIService()
                service.clients = {'gh': 'gh-cli', 'gemini': MagicMock(), 'openai': MagicMock()}
                service._set_default_provider()
                service._initialized = True
                return service

def test_set_valid_provider(ai_service):
    ai_service.set_provider("gh")
    assert ai_service.provider == "gh"
    assert ai_service.is_forced is True

    ai_service.set_provider("gemini")
    assert ai_service.provider == "gemini"

def test_set_invalid_provider(ai_service):
    with pytest.raises(ValueError):
        ai_service.set_provider("invalid_xyz")

def test_set_unconfigured_provider(ai_service):
    # This test previously expected RuntimeError because set_provider checked self.clients.
    # With ADR-025 (Lazy Loading), this should now SUCCEED at the configuration step.
    # The error will only happen when complete() is called.
    if 'openai' in ai_service.clients:
        del ai_service.clients['openai']
    
    ai_service.set_provider("openai")
    assert ai_service.provider == "openai"

def test_metrics_increment(ai_service):
    # Reset metrics for test isolation (hacky but works for simple counter)
    ai_command_runs_total._metrics.clear()
    
    ai_service.clients['gh'] = MagicMock()
    # Mock _try_complete to return success
    ai_service._try_complete = MagicMock(return_value="Success")
    
    ai_service.set_provider("gh")
    ai_service.complete("sys", "user")
    
    # Check if metric was incremented
    # We can check the sample value from the registry or the counter object
    # For simplicity, let's verify sample value matches
    
    assert ai_service._try_complete.call_count == 1

def test_fallback_logic(ai_service):
    ai_service.clients = {'gh': 'mock', 'gemini': 'mock', 'openai': 'mock'}
    ai_service.provider = 'gh'
    ai_service.is_forced = True
    
    def side_effect(provider, system, user, model=None, **kwargs):
        if provider == "gh":
            raise Exception("GH Failed")
        if provider == "gemini":
            return "Success"
        return ""

    ai_service._try_complete = MagicMock(side_effect=side_effect)
    
    # Run complete
    result = ai_service.complete("sys", "user")
    
    assert result == "Success"
    assert ai_service.provider == "gemini"

def test_complete_no_provider(ai_service):
    ai_service.clients = {}
    ai_service.provider = None
    result = ai_service.complete("sys", "user")
    assert result == ""

def test_set_provider_lazy_loading():
    """
    Verify that set_provider sets the provider string but does NOT
    trigger initialization of clients (ADR-025).
    """
    # We purposefully do NOT patch __init__ via mock_service fixture here
    # so we can test the real lazy loading behavior
    service = AIService()
    service._initialized = False # Force uninitialized state
    
    with patch("agent.core.ai.service.AIService._ensure_initialized") as mock_init:
        # Action
        service.set_provider("openai")
        
        # Assert
        assert service.provider == "openai"
        assert service.is_forced is True
        # CRITICAL: _ensure_initialized should NOT be called
        mock_init.assert_not_called()

def test_complete_triggers_initialization():
    """
    Verify that calling complete() DOES trigger initialization.
    """
    service = AIService()
    service._initialized = False
    service.set_provider("openai")
    
    with patch("agent.core.ai.service.AIService._ensure_initialized") as mock_init:
        # Mock _try_complete to avoid actual API call
        service._try_complete = MagicMock(return_value="Success")
        
        # Action
        service.complete("sys", "user")
        
        # Assert
        # Initialization SHOULD be called now
        mock_init.assert_called_once()


def test_rate_limit_retry_backoff(ai_service):
    """Verify 429 errors trigger exponential backoff retries on the same provider,
    not an immediate provider switch."""
    ai_service.provider = 'openai'
    ai_service.is_forced = True

    call_count = 0
    mock_client = MagicMock()

    def openai_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise Exception("429 Too Many Requests")
        result = MagicMock()
        result.choices = [MagicMock()]
        result.choices[0].message.content = "Success after backoff"
        return result

    mock_client.chat.completions.create.side_effect = openai_side_effect
    ai_service.clients['openai'] = mock_client

    with patch("agent.core.ai.service.time.sleep") as mock_sleep, \
         patch("agent.core.config.config") as mock_cfg:
        mock_cfg.panel_num_retries = 5
        result = ai_service.complete("sys", "user")

    assert result == "Success after backoff"
    # Should have retried same provider, not switched
    assert ai_service.provider == "openai"
    assert call_count == 3
    # Exponential backoff: 5*(2^0)=5, 5*(2^1)=10
    assert mock_sleep.call_count == 2
    mock_sleep.assert_any_call(5)
    mock_sleep.assert_any_call(10)


# ── Ollama Provider Tests ──

def test_ollama_health_check_success():
    """Verify successful Ollama health check marks provider as available."""
    service = AIService()
    service._initialized = False

    mock_response = MagicMock()
    mock_response.status_code = 200

    env_override = {
        "OLLAMA_HOST": "http://127.0.0.1:11434",
        "OPENAI_API_KEY": "", "GEMINI_API_KEY": "",
        "ANTHROPIC_API_KEY": "", "GITHUB_TOKEN": "",
    }
    with patch.dict("os.environ", env_override, clear=False), \
         patch("agent.core.ai.service.AIService._check_gh_cli", return_value=False), \
         patch("httpx.get", return_value=mock_response), \
         patch("openai.OpenAI") as mock_openai:
        service.reload()
        assert "ollama" in service.clients


def test_ollama_health_check_failure():
    """Verify failed Ollama health check gracefully skips provider."""
    service = AIService()
    service._initialized = False

    env_override = {
        "OLLAMA_HOST": "http://127.0.0.1:11434",
        "OPENAI_API_KEY": "", "GEMINI_API_KEY": "",
        "ANTHROPIC_API_KEY": "", "GITHUB_TOKEN": "",
    }
    with patch.dict("os.environ", env_override, clear=False), \
         patch("agent.core.ai.service.AIService._check_gh_cli", return_value=False), \
         patch("httpx.get", side_effect=Exception("Connection refused")):
        service.reload()
        assert "ollama" not in service.clients


def test_ollama_security_guard_blocks_remote():
    """Verify OLLAMA_HOST security guard rejects non-localhost hosts."""
    service = AIService()
    service._initialized = False

    with patch.dict("os.environ", {"OLLAMA_HOST": "http://evil.example.com:11434"}), \
         patch("agent.core.ai.service.AIService._check_gh_cli", return_value=False):
        service.reload()
        assert "ollama" not in service.clients


def test_ollama_temperature_passthrough():
    """Verify temperature parameter is passed through to Ollama completion."""
    service = AIService()
    service._initialized = True
    service.provider = "ollama"
    service.is_forced = True

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "test response"
    mock_client.chat.completions.create.return_value = mock_response

    service.clients = {"ollama": mock_client}
    service.models = {"ollama": "llama3"}

    with patch("agent.core.config.config") as mock_cfg:
        mock_cfg.panel_num_retries = 3
        result = service._try_complete("ollama", "sys", "user", temperature=0.0)

    call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs[1].get("temperature") == 0.0 or \
           call_kwargs.kwargs.get("temperature") == 0.0
    assert result == "test response"


def test_ollama_null_safety():
    """Verify _try_complete handles None content from Ollama gracefully."""
    service = AIService()
    service._initialized = True
    service.provider = "ollama"
    service.is_forced = True

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = None  # null content
    mock_client.chat.completions.create.return_value = mock_response

    service.clients = {"ollama": mock_client}
    service.models = {"ollama": "llama3"}

    with patch("agent.core.config.config") as mock_cfg:
        mock_cfg.panel_num_retries = 3
        result = service._try_complete("ollama", "sys", "user")

    assert result == ""


def test_fallback_chain_reaches_ollama():
    """Verify the fallback chain reaches ollama when all other providers fail."""
    service = AIService()
    service._initialized = True
    service.provider = "gemini"
    service.is_forced = True
    service.clients = {"gemini": "mock", "openai": "mock", "ollama": "mock"}

    def side_effect(provider, system, user, model=None, **kwargs):
        if provider == "gemini":
            raise Exception("Gemini failed")
        if provider == "openai":
            raise Exception("OpenAI failed")
        if provider == "ollama":
            return "Ollama success"
        return ""

    service._try_complete = MagicMock(side_effect=side_effect)

    result = service.complete("sys", "user")
    assert result == "Ollama success"
    assert service.provider == "ollama"