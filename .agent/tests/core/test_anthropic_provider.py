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
def ai_service_with_anthropic():
    """Fixture that includes Anthropic in the initialized clients."""
    with patch.dict("os.environ", {
        "OPENAI_API_KEY": "dummy",
        "GOOGLE_GEMINI_API_KEY": "dummy",
        "ANTHROPIC_API_KEY": "dummy"
    }):
        with patch("agent.core.ai.service.AIService._check_gh_cli", return_value=True):
            with patch("openai.OpenAI"), patch("google.genai.Client"), patch("anthropic.Anthropic"):
                service = AIService()
                service.clients = {
                    'gh': 'gh-cli',
                    'gemini': MagicMock(),
                    'openai': MagicMock(),
                    'anthropic': MagicMock()
                }
                service._set_default_provider()
                service._initialized = True
                return service


def test_anthropic_in_valid_providers():
    """Test that anthropic is included in the valid providers list."""
    from agent.core.config import get_valid_providers
    valid_providers = get_valid_providers()
    assert "anthropic" in valid_providers


def test_set_anthropic_provider(ai_service_with_anthropic):
    """Test setting Anthropic as the active provider."""
    ai_service_with_anthropic.set_provider("anthropic")
    assert ai_service_with_anthropic.provider == "anthropic"
    assert ai_service_with_anthropic.is_forced is True


def test_anthropic_unconfigured():
    """Test that unconfigured Anthropic raises RuntimeError on usage (Lazy Loading)."""
    with patch.dict("os.environ", {}, clear=True): # Clear env to prevent fallback to OTHER providers
        with patch("agent.core.ai.service.AIService._check_gh_cli", return_value=False):
            with patch("openai.OpenAI"):
                # Mock get_secret to return None, simulating no keys found
                with patch("agent.core.ai.service.get_secret", return_value=None):
                    service = AIService()
                    service.clients = {'openai': MagicMock()}
                    service._set_default_provider()
                    
                    # Should succeed now (Lazy)
                    service.set_provider("anthropic")
                    assert service.provider == "anthropic"

                    # Did not initialize yet
                    assert 'anthropic' not in service.clients

                    # Ensure fallback doesn't save us (remove openai mock)
                    service.clients = {}

                    # Should fail when we try to use it because NO providers are available
                    # Raises KeyError because we forced 'anthropic' but removed the client
                    with pytest.raises(Exception) as exc_info:
                        service.complete("sys", "user")
                    assert isinstance(exc_info.value, Exception)


def test_anthropic_metrics_increment(ai_service_with_anthropic):
    """Test that Anthropic provider increments metrics correctly."""
    # Reset metrics for test isolation
    ai_command_runs_total._metrics.clear()
    
    ai_service_with_anthropic._try_complete = MagicMock(return_value="Anthropic Success")
    
    ai_service_with_anthropic.set_provider("anthropic")
    ai_service_with_anthropic.complete("sys", "user")
    
    val = ai_command_runs_total.labels(provider='anthropic')._value.get()
    assert val == 1


def test_fallback_to_anthropic(ai_service_with_anthropic):
    """Test that fallback chain reaches anthropic when other providers fail."""
    ai_service_with_anthropic.provider = 'gh'
    
    def side_effect(provider, system, user, model=None):
        if provider in ["gh", "gemini", "openai"]:
            raise Exception(f"{provider} Failed")
        if provider == "anthropic":
            return "Anthropic Success"
        return ""

    ai_service_with_anthropic._try_complete = MagicMock(side_effect=side_effect)
    
    result = ai_service_with_anthropic.complete("sys", "user")
    
    assert result == "Anthropic Success"
    assert ai_service_with_anthropic.provider == "anthropic"


def test_anthropic_completion_streaming():
    """Test Anthropic streaming completion with mocked client."""
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test_key"}):
        with patch("anthropic.Anthropic") as mock_anthropic_class:
            # Mock the streaming response
            mock_stream = MagicMock()
            mock_stream.__enter__ = MagicMock(return_value=mock_stream)
            mock_stream.__exit__ = MagicMock(return_value=False)
            mock_stream.text_stream = ["Hello", " ", "World", "!"]
            
            mock_client = MagicMock()
            mock_client.messages.stream.return_value = mock_stream
            mock_anthropic_class.return_value = mock_client
            
            # Create service (will init anthropic client)
            with patch("agent.core.ai.service.AIService._check_gh_cli", return_value=False):
                service = AIService()
                service.reload()
                service._initialized = True
                
                # Verify client was created
                assert 'anthropic' in service.clients
                
                # Call _try_complete for anthropic
                result = service._try_complete(
                    "anthropic",
                    "system prompt",
                    "user prompt",
                    "claude-sonnet-4-5-20250929"
                )
                
                assert result == "Hello World!"
                mock_client.messages.stream.assert_called_once()
                call_kwargs = mock_client.messages.stream.call_args[1]
                assert call_kwargs['model'] == "claude-sonnet-4-5-20250929"
                assert call_kwargs['system'] == "system prompt"
                assert call_kwargs['messages'][0]['content'] == "user prompt"


def test_anthropic_default_model():
    """Test that Anthropic has the correct default model configured."""
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test_key"}):
        with patch("anthropic.Anthropic"):
            with patch("agent.core.ai.service.AIService._check_gh_cli", return_value=False):
                service = AIService()
                
                assert 'anthropic' in service.models
                assert service.models['anthropic'] == 'claude-sonnet-4-5-20250929'


def test_anthropic_in_fallback_chain():
    """Test that Anthropic is included in the fallback chain."""
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test_key"}):
        with patch("anthropic.Anthropic"):
            with patch("agent.core.ai.service.AIService._check_gh_cli", return_value=False):
                service = AIService()
                
                # Add all providers to clients
                service.clients = {'gh': 'mock', 'gemini': 'mock', 'openai': 'mock', 'anthropic': 'mock'}
                service.provider = 'openai'
                
                # Verify switch works
                success = service.try_switch_provider('openai')
                assert success is True
                assert service.provider == 'anthropic'
