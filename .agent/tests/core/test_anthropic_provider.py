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
"""Unit tests for AnthropicProvider."""

import asyncio
import pytest
from unittest.mock import MagicMock
from agent.core.ai.protocols import AIRateLimitError
from agent.core.ai.providers.anthropic import AnthropicProvider


def test_anthropic_generate_assembles_stream():
    """Test that generate calls stream and joins text."""
    mock_client = MagicMock()
    provider = AnthropicProvider(client=mock_client, model_name="claude-3")
    
    mock_stream = MagicMock()
    mock_stream.text_stream = ["Hello", " world"]
    mock_client.messages.stream.return_value.__enter__.return_value = mock_stream
    
    result = asyncio.run(provider.generate("hi"))
    assert result == "Hello world"


def test_anthropic_raises_rate_limit():
    """Test 429 error mapping for Anthropic."""
    mock_client = MagicMock()
    provider = AnthropicProvider(client=mock_client, model_name="claude-3")
    mock_client.messages.stream.side_effect = Exception("429 Overloaded")
    
    with pytest.raises(AIRateLimitError):
        asyncio.run(provider.generate("hi"))