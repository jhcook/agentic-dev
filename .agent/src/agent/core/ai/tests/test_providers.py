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

"""Unit tests for the core/ai/providers package (INFRA-108).

Covers protocol compliance, factory dispatch, prefix fallback, and
generate/stream stub behaviour for MockProvider.
"""

import asyncio
import pytest

from agent.core.ai.protocols import AIProvider, AIRateLimitError
from agent.core.ai.providers import get_provider
from agent.core.ai.providers.openai import OpenAIProvider
from agent.core.ai.providers.vertex import VertexAIProvider
from agent.core.ai.providers.mock import MockProvider


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------

def test_openai_provider_implements_protocol():
    """OpenAIProvider must be a runtime-checkable AIProvider."""
    assert isinstance(OpenAIProvider(model_name="gpt-4o"), AIProvider)


def test_vertex_provider_implements_protocol():
    """VertexAIProvider must be a runtime-checkable AIProvider."""
    assert isinstance(VertexAIProvider(model_name="gemini-1.5-pro"), AIProvider)


def test_mock_provider_implements_protocol():
    """MockProvider must be a runtime-checkable AIProvider."""
    assert isinstance(MockProvider(model_name="mock"), AIProvider)


# ---------------------------------------------------------------------------
# Factory / registry — provider name dispatch
# ---------------------------------------------------------------------------

def test_get_provider_openai_by_name():
    """get_provider('openai') returns an OpenAIProvider."""
    provider = get_provider("openai")
    assert isinstance(provider, OpenAIProvider)


def test_get_provider_vertex_by_name():
    """get_provider('vertex') returns a VertexAIProvider."""
    provider = get_provider("vertex")
    assert isinstance(provider, VertexAIProvider)


def test_get_provider_gemini_by_name():
    """get_provider('gemini') also returns a VertexAIProvider (same SDK)."""
    provider = get_provider("gemini")
    assert isinstance(provider, VertexAIProvider)


def test_get_provider_mock_by_name():
    """get_provider('mock') returns a MockProvider."""
    provider = get_provider("mock")
    assert isinstance(provider, MockProvider)


# ---------------------------------------------------------------------------
# Factory — model-name prefix fallback
# ---------------------------------------------------------------------------

def test_get_provider_prefix_fallback_gpt():
    """get_provider falls back to OpenAI for unknown gpt- prefixed model names."""
    provider = get_provider("gpt-99-turbo")
    assert isinstance(provider, OpenAIProvider)


def test_get_provider_prefix_fallback_gemini():
    """get_provider falls back to Vertex for unknown gemini- prefixed model names."""
    provider = get_provider("gemini-2.0-flash")
    assert isinstance(provider, VertexAIProvider)


def test_get_provider_unknown_defaults_to_openai():
    """get_provider defaults to OpenAI for completely unknown model names."""
    provider = get_provider("some-unknown-model-xyz")
    assert isinstance(provider, OpenAIProvider)


# ---------------------------------------------------------------------------
# MockProvider generate / stream behaviour
# ---------------------------------------------------------------------------

def test_mock_provider_generate():
    """MockProvider.generate returns the mock response string."""
    provider = MockProvider(model_name="mock")
    result = asyncio.run(provider.generate("hello"))
    assert result == "Mock response"


def test_mock_provider_generate_force_error():
    """MockProvider.generate raises AIRateLimitError when force_error kwarg is set."""
    provider = MockProvider(model_name="mock")
    with pytest.raises(AIRateLimitError):
        asyncio.run(provider.generate("hello", force_error=True))


def test_mock_provider_stream():
    """MockProvider.stream yields the expected chunks."""
    provider = MockProvider(model_name="mock")

    async def _collect() -> list:
        """Collect all chunks from the mock stream."""
        return [chunk async for chunk in provider.stream("hello")]

    chunks = asyncio.run(_collect())
    assert chunks == ["Mock ", "stream"]


# ---------------------------------------------------------------------------
# supports_tools / get_models
# ---------------------------------------------------------------------------

def test_base_provider_supports_tools_false_by_default():
    """BaseProvider.supports_tools returns False by default."""
    provider = MockProvider(model_name="mock")
    assert provider.supports_tools() is False


def test_openai_provider_supports_tools_true():
    """OpenAIProvider.supports_tools returns True."""
    provider = OpenAIProvider(model_name="gpt-4o")
    assert provider.supports_tools() is True


def test_base_provider_get_models_returns_model_name():
    """BaseProvider.get_models returns a list containing the model name."""
    provider = OpenAIProvider(model_name="gpt-4o")
    assert "gpt-4o" in provider.get_models()
