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
    with patch.dict("os.environ", {"OPENAI_API_KEY": "dummy", "GOOGLE_GEMINI_API_KEY": "dummy"}):
        with patch("agent.core.ai.service.AIService._check_gh_cli", return_value=True):
            with patch("openai.OpenAI"), patch("google.genai.Client"):
                service = AIService()
                service.clients = {'gh': 'gh-cli', 'gemini': MagicMock(), 'openai': MagicMock()}
                service._set_default_provider()
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
    del ai_service.clients['openai']
    with pytest.raises(RuntimeError):
        ai_service.set_provider("openai")

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
    
    val = ai_command_runs_total.labels(provider='gh')._value.get()
    assert val == 1.0

def test_fallback_logic(ai_service):
    ai_service.clients = {'gh': 'mock', 'gemini': 'mock', 'openai': 'mock'}
    ai_service.provider = 'gh'
    
    def side_effect(provider, system, user, model=None):
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