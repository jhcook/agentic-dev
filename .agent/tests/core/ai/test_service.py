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
from unittest.mock import MagicMock, patch
from agent.core.ai.service import AIService

@pytest.fixture
def mock_service():
    with patch("agent.core.ai.service.AIService.__init__", return_value=None):
        service = AIService()
        service.provider = "gemini"
        service.models = {"gemini": "gemini-pro", "openai": "gpt-4"}
        service.clients = {}
        service.is_forced = False
        service._initialized = True  # Skip lazy init in tests
        # Simple round-robin chain for testing
        service._provider_chain = ["gemini", "openai", "anthropic"]
        return service

@pytest.mark.skip(reason="Demonstration test - remove when real tests exist.")
def test_complete_failover_on_rate_limit(mock_service):
    """Test that 429 triggers immediate failover to next provider."""
    
    # Mock _try_complete to raise 429 on first call (gemini)
    # and succeed on second call (openai)
    
    def side_effect(provider, *args, **kwargs):
        if provider == "gemini":
            raise Exception("429 Resource exhausted")
        if provider == "openai":
            return "Success response"
        raise Exception("Should not reach here")

    mock_service._try_complete = MagicMock(side_effect=side_effect)
    
    # Mock switch logic (simple replacement for test)
    def switch(current):
        if current == "gemini":
            mock_service.provider = "openai"
            return True
        return False
        
    mock_service.try_switch_provider = MagicMock(side_effect=switch)
    
    # Execute
    result = mock_service.complete("sys", "user")
    
    assert result == "Success response"
    
    # Verify sequence
    # 1. Called with gemini
    # 2. Raised 429
    # 3. Called try_switch_provider("gemini")
    # 4. Called with openai
    
    # Just verify try_switch_provider argument
    mock_service.try_switch_provider.assert_called_with("gemini")

@pytest.mark.xfail(
    reason="INFRA-100 refactored service dispatch; try_switch_provider is no longer "
           "called directly from complete(). Needs test rewrite against new dispatch path.",
    strict=False,
)
def test_complete_unknown_error_retries_provider(mock_service):
    """Verify generic errors trigger provider switch."""
    mock_service._try_complete = MagicMock(side_effect=Exception("500 Internal Error"))
    mock_service.try_switch_provider = MagicMock(return_value=False)

    with pytest.raises(Exception):
        mock_service.complete("sys", "user")

    assert mock_service.try_switch_provider.call_count > 0

@pytest.mark.xfail(
    reason="INFRA-100 refactored service dispatch; try_switch_provider is no longer "
           "called directly from complete(). Needs test rewrite against new dispatch path.",
    strict=False,
)
def test_try_complete_fail_fast_on_429(mock_service):
    """Verify 429 triggers a provider switch."""
    mock_service._try_complete = MagicMock(side_effect=Exception("429 Resource exhausted"))
    mock_service.try_switch_provider = MagicMock(return_value=True)

    try:
        mock_service.complete("sys", "user")
    except Exception:
        pass

    mock_service.try_switch_provider.assert_called_with("gemini")