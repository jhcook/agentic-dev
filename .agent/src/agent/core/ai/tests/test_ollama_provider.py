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
"""Unit tests for OllamaProvider (INFRA-108).

Covers generate(), stream(), localhost security guard, and typed error mapping.
"""
import asyncio
from unittest.mock import MagicMock

import pytest

from agent.core.ai.protocols import AIConfigurationError, AIConnectionError, AIRateLimitError
from agent.core.ai.providers.ollama import OllamaProvider


def _make_provider(model_name: str = "llama3", base_url: str = "http://localhost:11434/v1") -> OllamaProvider:
    """Return an OllamaProvider with a mocked OpenAI-compat SDK client."""
    mock_client = MagicMock()
    mock_client.base_url = base_url
    return OllamaProvider(client=mock_client, model_name=model_name)


# ---------------------------------------------------------------------------
# Security guard
# ---------------------------------------------------------------------------

def test_remote_host_raises_configuration_error():
    """OllamaProvider.__init__ raises AIConfigurationError for non-localhost hosts."""
    mock_client = MagicMock()
    mock_client.base_url = "http://remote-server.example.com:11434/v1"

    with pytest.raises(AIConfigurationError, match="not localhost"):
        OllamaProvider(client=mock_client, model_name="llama3")


def test_localhost_host_accepted():
    """OllamaProvider.__init__ accepts 127.0.0.1 as a localhost address."""
    mock_client = MagicMock()
    mock_client.base_url = "http://127.0.0.1:11434/v1"
    provider = OllamaProvider(client=mock_client, model_name="llama3")
    assert provider.model_name == "llama3"


# ---------------------------------------------------------------------------
# generate()
# ---------------------------------------------------------------------------

def test_generate_returns_content():
    """generate() returns the message content from the Ollama API response."""
    provider = _make_provider()
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="Ollama says hi"))]
    provider.client.chat.completions.create.return_value = mock_resp

    result = asyncio.run(provider.generate("hey"))
    assert result == "Ollama says hi"


def test_generate_raises_rate_limit_on_429():
    """generate() raises AIRateLimitError on rate-limit errors."""
    provider = _make_provider()
    provider.client.chat.completions.create.side_effect = Exception("429 rate limit exceeded")

    with pytest.raises(AIRateLimitError):
        asyncio.run(provider.generate("hey"))


def test_generate_raises_connection_error_on_refused():
    """generate() raises AIConnectionError when Ollama is unreachable."""
    provider = _make_provider()
    provider.client.chat.completions.create.side_effect = Exception("connection refused")

    with pytest.raises(AIConnectionError):
        asyncio.run(provider.generate("hey"))


def test_generate_raises_connection_error_when_no_client():
    """generate() raises AIConnectionError when client is None."""
    provider = OllamaProvider(client=None, model_name="llama3")

    with pytest.raises(AIConnectionError):
        asyncio.run(provider.generate("hey"))


# ---------------------------------------------------------------------------
# stream()
# ---------------------------------------------------------------------------

def test_stream_yields_chunks():
    """stream() yields content chunks from the Ollama streaming API."""
    provider = _make_provider()
    chunk1 = MagicMock()
    chunk1.choices = [MagicMock(delta=MagicMock(content="chunk1"))]
    chunk2 = MagicMock()
    chunk2.choices = [MagicMock(delta=MagicMock(content="chunk2"))]
    provider.client.chat.completions.create.return_value = iter([chunk1, chunk2])

    async def _collect() -> list:
        """Collect all streamed chunks."""
        return [c async for c in provider.stream("hey")]

    chunks = asyncio.run(_collect())
    assert chunks == ["chunk1", "chunk2"]


# ---------------------------------------------------------------------------
# supports_tools / get_models
# ---------------------------------------------------------------------------

def test_supports_tools_returns_false():
    """OllamaProvider.supports_tools returns False."""
    provider = _make_provider()
    assert provider.supports_tools() is False


def test_get_models_contains_model_name():
    """get_models returns a list containing the configured model name."""
    provider = _make_provider("llama3.2")
    assert "llama3.2" in provider.get_models()
