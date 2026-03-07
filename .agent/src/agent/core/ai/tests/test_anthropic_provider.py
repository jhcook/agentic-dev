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
"""Unit tests for AnthropicProvider (INFRA-108).

Covers generate(), stream(), and typed error mapping.
"""
import asyncio
from unittest.mock import MagicMock

import pytest

from agent.core.ai.protocols import AIConnectionError, AIRateLimitError
from agent.core.ai.providers.anthropic import AnthropicProvider


def _make_provider(model_name: str = "claude-3-5-sonnet-20241022") -> AnthropicProvider:
    """Return an AnthropicProvider with a mocked SDK client."""
    mock_client = MagicMock()
    return AnthropicProvider(client=mock_client, model_name=model_name)


# ---------------------------------------------------------------------------
# generate()
# ---------------------------------------------------------------------------

def test_generate_assembles_stream_text():
    """generate() joins all text chunks from the streaming API into one string."""
    provider = _make_provider()

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__enter__.return_value.text_stream = ["Hello", " world"]
    mock_stream_ctx.__exit__.return_value = False
    provider.client.messages.stream.return_value = mock_stream_ctx

    result = asyncio.run(provider.generate("hi"))
    assert result == "Hello world"


def test_generate_with_system_prompt_passes_system_kwarg():
    """generate() passes system_prompt as 'system' kwarg to the API."""
    provider = _make_provider()

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__enter__.return_value.text_stream = ["ok"]
    mock_stream_ctx.__exit__.return_value = False
    provider.client.messages.stream.return_value = mock_stream_ctx

    asyncio.run(provider.generate("prompt", system_prompt="Be helpful"))

    call_kwargs = provider.client.messages.stream.call_args[1]
    assert call_kwargs.get("system") == "Be helpful"


def test_generate_raises_rate_limit_on_429():
    """generate() raises AIRateLimitError on 429 Overloaded responses."""
    provider = _make_provider()
    provider.client.messages.stream.side_effect = Exception("429 Overloaded")

    with pytest.raises(AIRateLimitError):
        asyncio.run(provider.generate("hi"))


def test_generate_raises_rate_limit_on_overloaded():
    """generate() raises AIRateLimitError when 'overloaded' appears in error."""
    provider = _make_provider()
    provider.client.messages.stream.side_effect = Exception("Service Overloaded")

    with pytest.raises(AIRateLimitError):
        asyncio.run(provider.generate("hi"))


def test_generate_raises_connection_error_on_timeout():
    """generate() raises AIConnectionError on timeout/network errors."""
    provider = _make_provider()
    provider.client.messages.stream.side_effect = Exception("connection timeout")

    with pytest.raises(AIConnectionError):
        asyncio.run(provider.generate("hi"))


def test_generate_raises_connection_error_when_no_client():
    """generate() raises AIConnectionError when client is None."""
    provider = AnthropicProvider(client=None, model_name="claude-3-5-sonnet-20241022")

    with pytest.raises(AIConnectionError):
        asyncio.run(provider.generate("hi"))


# ---------------------------------------------------------------------------
# stream()
# ---------------------------------------------------------------------------

def test_stream_yields_text_chunks():
    """stream() yields each text chunk from the streaming API."""
    provider = _make_provider()

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__enter__.return_value.text_stream = ["Hello", " world"]
    mock_stream_ctx.__exit__.return_value = False
    provider.client.messages.stream.return_value = mock_stream_ctx

    async def _collect() -> list:
        """Collect all streamed chunks."""
        return [c async for c in provider.stream("hi")]

    chunks = asyncio.run(_collect())
    assert chunks == ["Hello", " world"]


# ---------------------------------------------------------------------------
# supports_tools / get_models
# ---------------------------------------------------------------------------

def test_supports_tools_returns_false():
    """AnthropicProvider.supports_tools returns False (no tool calling)."""
    provider = _make_provider()
    assert provider.supports_tools() is False


def test_get_models_contains_model_name():
    """get_models returns a list that includes the configured model name."""
    provider = _make_provider("claude-3-5-haiku-20241022")
    assert "claude-3-5-haiku-20241022" in provider.get_models()
