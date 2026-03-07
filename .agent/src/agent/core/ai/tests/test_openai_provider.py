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
"""Unit tests for OpenAIProvider (INFRA-108).

Covers generate(), stream(), supports_tools(), and typed error mapping.
"""
import asyncio
from unittest.mock import MagicMock

import pytest

from agent.core.ai.protocols import AIConnectionError, AIRateLimitError
from agent.core.ai.providers.openai import OpenAIProvider


def _make_provider(model_name: str = "gpt-4o") -> OpenAIProvider:
    """Return an OpenAIProvider with a mocked SDK client."""
    mock_client = MagicMock()
    return OpenAIProvider(client=mock_client, model_name=model_name)


# ---------------------------------------------------------------------------
# generate()
# ---------------------------------------------------------------------------

def test_generate_returns_content():
    """generate() returns the message content from the API response."""
    provider = _make_provider()
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="Hello!"))]
    provider.client.chat.completions.create.return_value = mock_resp

    result = asyncio.run(provider.generate("prompt"))
    assert result == "Hello!"


def test_generate_with_system_prompt_passes_system_message():
    """generate() includes the system message when system_prompt is provided."""
    provider = _make_provider()
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="ok"))]
    provider.client.chat.completions.create.return_value = mock_resp

    asyncio.run(provider.generate("hello", system_prompt="Act as a helpful bot"))

    call_kwargs = provider.client.chat.completions.create.call_args[1]
    messages = call_kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "Act as a helpful bot"


def test_generate_raises_rate_limit_on_429():
    """generate() raises AIRateLimitError when the SDK raises a 429 error."""
    provider = _make_provider()
    provider.client.chat.completions.create.side_effect = Exception("429 Too Many Requests")

    with pytest.raises(AIRateLimitError):
        asyncio.run(provider.generate("prompt"))


def test_generate_raises_connection_error_on_network_failure():
    """generate() raises AIConnectionError on connection failures."""
    provider = _make_provider()
    provider.client.chat.completions.create.side_effect = Exception("connection refused")

    with pytest.raises(AIConnectionError):
        asyncio.run(provider.generate("prompt"))


def test_generate_raises_connection_error_when_no_client():
    """generate() raises AIConnectionError when client is None."""
    provider = OpenAIProvider(client=None, model_name="gpt-4o")

    with pytest.raises(AIConnectionError):
        asyncio.run(provider.generate("prompt"))


def test_generate_returns_empty_string_on_empty_choices():
    """generate() returns '' when the API response has no choices."""
    provider = _make_provider()
    mock_resp = MagicMock()
    mock_resp.choices = []
    provider.client.chat.completions.create.return_value = mock_resp

    result = asyncio.run(provider.generate("prompt"))
    assert result == ""


# ---------------------------------------------------------------------------
# stream()
# ---------------------------------------------------------------------------

def test_stream_yields_chunks():
    """stream() yields content from each delta chunk."""
    provider = _make_provider()
    chunk1 = MagicMock()
    chunk1.choices = [MagicMock(delta=MagicMock(content="Hello "))]
    chunk2 = MagicMock()
    chunk2.choices = [MagicMock(delta=MagicMock(content="world"))]
    provider.client.chat.completions.create.return_value = iter([chunk1, chunk2])

    async def _collect() -> list:
        """Collect all streamed chunks."""
        return [c async for c in provider.stream("prompt")]

    chunks = asyncio.run(_collect())
    assert chunks == ["Hello ", "world"]


def test_stream_skips_empty_delta_content():
    """stream() skips chunks where delta.content is None or empty."""
    provider = _make_provider()
    chunk_empty = MagicMock()
    chunk_empty.choices = [MagicMock(delta=MagicMock(content=None))]
    chunk_real = MagicMock()
    chunk_real.choices = [MagicMock(delta=MagicMock(content="data"))]
    provider.client.chat.completions.create.return_value = iter([chunk_empty, chunk_real])

    async def _collect() -> list:
        """Collect all non-empty streamed chunks."""
        return [c async for c in provider.stream("prompt")]

    chunks = asyncio.run(_collect())
    assert chunks == ["data"]


# ---------------------------------------------------------------------------
# supports_tools / get_models
# ---------------------------------------------------------------------------

def test_supports_tools_returns_true():
    """OpenAIProvider.supports_tools returns True."""
    provider = _make_provider()
    assert provider.supports_tools() is True


def test_get_models_contains_model_name():
    """get_models returns a list that includes the configured model name."""
    provider = _make_provider("gpt-4o-mini")
    assert "gpt-4o-mini" in provider.get_models()
