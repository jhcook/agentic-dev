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
from unittest.mock import patch, MagicMock
from pathlib import Path
from agent.core.router import SmartRouter

# Mock configuration for testing
MOCK_ROUTER_CONFIG = {
    "models": {
        "gpt-4o": {
            "provider": "openai",
            "deployment_id": "gpt-4o",
            "tier": "advanced",
            "context_window": 128000,
            "cost_per_1k_input": 0.0025
        },
        "gpt-4o-mini": {
            "provider": "openai",
            "deployment_id": "gpt-4o-mini",
            "tier": "light",
            "context_window": 128000,
            "cost_per_1k_input": 0.00015
        },
        "gemini-1.5-flash": {
            "provider": "gemini",
            "deployment_id": "gemini-1.5-flash-latest",
            "tier": "standard",
            "context_window": 1000000,
            "cost_per_1k_input": 0.000075
        }
    },
    "settings": {
        "default_tier": "standard"
    }
}

@pytest.fixture
def mock_router():
    with patch("agent.core.router.SmartRouter._load_config", return_value=MOCK_ROUTER_CONFIG):
        router = SmartRouter(config_path=Path("dummy"))
        return router

@patch("agent.core.router.token_manager")
def test_route_standard_tier_optimizes_cost(mock_tokens, mock_router):
    # Given: A standard request with low tokens
    mock_tokens.count_tokens.return_value = 100
    
    # When: We route for "standard" tier
    # Candidates: gemini-1.5-flash (standard, $0.000075), gpt-4o (advanced, $0.0025)
    # gpt-4o-mini is excluded (light < standard)
    result = mock_router.route("test prompt", tier="standard")
    
    # Then: Should pick Gemini Flash (cheapest standard+)
    assert result["key"] == "gemini-1.5-flash"
    assert result["provider"] == "gemini"

@patch("agent.core.router.token_manager")
def test_route_light_tier_finds_cheapest(mock_tokens, mock_router):
    # Given: A light request
    mock_tokens.count_tokens.return_value = 100
    
    # When: We route for "light" tier
    # Candidates: all models (light, standard, advanced)
    # Cheapest is Gemini Flash ($0.000075) vs Mini ($0.00015)
    result = mock_router.route("test prompt", tier="light")
    
    # Then: Should pick Gemini Flash
    assert result["key"] == "gemini-1.5-flash"

@patch("agent.core.router.token_manager")
def test_route_advanced_tier_excludes_others(mock_tokens, mock_router):
    # Given: An advanced request
    mock_tokens.count_tokens.return_value = 100
    
    # When: We route for "advanced" tier
    # Candidates: only gpt-4o
    result = mock_router.route("test prompt", tier="advanced")
    
    # Then: Should pick GPT-4o
    assert result["key"] == "gpt-4o"

@patch("agent.core.router.token_manager")
def test_route_context_window_limit(mock_tokens, mock_router):
    # Given: A huge prompt (e.g. 500k tokens)
    mock_tokens.count_tokens.return_value = 500000
    
    # When: We route for "standard"
    # gpt-4o (128k) -> Excluded
    # gpt-4o-mini (128k) -> Excluded
    # gemini-1.5-flash (1m) -> Included
    result = mock_router.route("huge prompt", tier="standard")
    
    # Then: Should pick Gemini Flash (only one that fits)
    assert result["key"] == "gemini-1.5-flash"
