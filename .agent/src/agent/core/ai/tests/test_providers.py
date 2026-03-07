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

"""Unit tests for core/ai/providers.py (INFRA-100)."""

import asyncio
import pytest

from agent.core.ai.protocols import AIProvider, AIRateLimitError
from agent.core.ai.providers import (
    OpenAIProvider,
    VertexAIProvider,
    MockProvider,
    get_provider,
)


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------

def test_openai_provider_implements_protocol():
    """OpenAIProvider must be a runtime-checkable AIProvider."""
    assert isinstance(OpenAIProvider("gpt-4o"), AIProvider)


def test_vertex_provider_implements_protocol():
    """VertexAIProvider must be a runtime-checkable AIProvider."""
    assert isinstance(VertexAIProvider("gemini-1.5-pro"), AIProvider)


def test_mock_provider_implements_protocol():
    """MockProvider must be a runtime-checkable AIProvider."""
    assert isinstance(MockProvider("mock"), AIProvider)


# ---------------------------------------------------------------------------
# Factory / registry
# ---------------------------------------------------------------------------

def test_get_provider_known_model_openai():
    """get_provider returns an OpenAIProvider for a known GPT model."""
    provider = get_provider("gpt-4o")
    assert isinstance(provider, OpenAIProvider)


def test_get_provider_known_model_vertex():
    """get_provider returns a VertexAIProvider for a known Gemini model."""
    provider = get_provider("gemini-1.5-pro")
    assert isinstance(provider, VertexAIProvider)


def test_get_provider_prefix_fallback_gpt():
    """get_provider falls back to OpenAI for unknown gpt- prefixed models."""
    provider = get_provider("gpt-99-turbo")
    assert isinstance(provider, OpenAIProvider)


def test_get_provider_prefix_fallback_gemini():
    """get_provider falls back to Vertex for unknown gemini- prefixed models."""
    provider = get_provider("gemini-2.0-flash")
    assert isinstance(provider, VertexAIProvider)


def test_get_provider_unknown_defaults_to_openai():
    """get_provider defaults to OpenAI for completely unknown model names."""
    provider = get_provider("some-unknown-model-xyz")
    assert isinstance(provider, OpenAIProvider)


# ---------------------------------------------------------------------------
# generate / stream stubs
# ---------------------------------------------------------------------------

def test_mock_provider_generate():
    """MockProvider.generate returns the mock response string."""
    provider = MockProvider("mock")
    result = asyncio.run(provider.generate("hello"))
    assert result == "Mock response"


def test_mock_provider_generate_force_error():
    """MockProvider.generate raises AIRateLimitError when force_error kwarg is set."""
    provider = MockProvider("mock")
    with pytest.raises(AIRateLimitError):
        asyncio.run(provider.generate("hello", force_error=True))


def test_mock_provider_stream():
    """MockProvider.stream yields the expected chunks."""
    provider = MockProvider("mock")

    async def _collect():
        return [chunk async for chunk in provider.stream("hello")]

    chunks = asyncio.run(_collect())
    assert chunks == ["Mock ", "stream"]


def test_openai_provider_generate_returns_string():
    """OpenAIProvider.generate returns a non-empty string (stub)."""
    provider = OpenAIProvider("gpt-4o")
    result = asyncio.run(provider.generate("test prompt"))
    assert isinstance(result, str) and len(result) > 0


def test_vertex_provider_generate_returns_string():
    """VertexAIProvider.generate returns a non-empty string (stub)."""
    provider = VertexAIProvider("gemini-1.5-pro")
    result = asyncio.run(provider.generate("test prompt"))
    assert isinstance(result, str) and len(result) > 0


# ---------------------------------------------------------------------------
# supports_tools / get_models
# ---------------------------------------------------------------------------

def test_base_provider_supports_tools_false_by_default():
    """BaseProvider.supports_tools returns False by default."""
    provider = MockProvider("mock")
    assert provider.supports_tools() is False


def test_base_provider_get_models_returns_model_name():
    """BaseProvider.get_models returns a list containing the model name."""
    provider = OpenAIProvider("gpt-4o")
    assert "gpt-4o" in provider.get_models()
