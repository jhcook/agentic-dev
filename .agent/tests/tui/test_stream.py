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

"""Tests for AIService.stream_complete() (INFRA-087).

Tests streaming behaviour with mocked provider clients, including
chunk concatenation, provider-specific paths, and disconnect recovery.
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def ai_service():
    """Return a fresh AIService with mocked initialization."""
    from agent.core.ai.service import AIService

    svc = AIService()
    svc._initialized = True
    svc.models = {
        "gemini": "gemini-2.5-pro",
        "vertex": "gemini-2.5-pro",
        "anthropic": "claude-sonnet-4-20250514",
        "openai": "gpt-4o",
        "ollama": "llama3",
    }
    svc.clients = {}
    return svc


class TestGeminiStreaming:
    """Test streaming for gemini/vertex providers."""

    def test_yields_text_chunks(self, ai_service):
        ai_service.provider = "gemini"

        mock_chunk1 = MagicMock()
        mock_chunk1.text = "Hello "
        mock_chunk2 = MagicMock()
        mock_chunk2.text = "world!"
        mock_chunk3 = MagicMock()
        mock_chunk3.text = None  # empty chunk should be skipped

        mock_client = MagicMock()
        mock_client.models.generate_content_stream.return_value = [
            mock_chunk1, mock_chunk2, mock_chunk3,
        ]

        with patch.object(ai_service, "_build_genai_client", return_value=mock_client):
            chunks = list(ai_service.stream_complete("system", "user"))

        assert chunks == ["Hello ", "world!"]
        assert "".join(chunks) == "Hello world!"

    def test_vertex_uses_same_path(self, ai_service):
        ai_service.provider = "vertex"

        mock_chunk = MagicMock()
        mock_chunk.text = "vertex response"

        mock_client = MagicMock()
        mock_client.models.generate_content_stream.return_value = [mock_chunk]

        with patch.object(ai_service, "_build_genai_client", return_value=mock_client):
            chunks = list(ai_service.stream_complete("system", "user"))

        assert chunks == ["vertex response"]


class TestAnthropicStreaming:
    """Test streaming for anthropic provider."""

    def test_yields_text_stream(self, ai_service):
        ai_service.provider = "anthropic"

        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.text_stream = iter(["chunk1", "chunk2", "chunk3"])

        mock_client = MagicMock()
        mock_client.messages.stream.return_value = mock_stream
        ai_service.clients["anthropic"] = mock_client

        chunks = list(ai_service.stream_complete("system", "user"))

        assert chunks == ["chunk1", "chunk2", "chunk3"]
        assert "".join(chunks) == "chunk1chunk2chunk3"


class TestOpenAIStreaming:
    """Test streaming for openai/ollama providers."""

    def test_yields_delta_content(self, ai_service):
        ai_service.provider = "openai"

        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta.content = "open"

        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta.content = "ai"

        chunk3 = MagicMock()
        chunk3.choices = []  # empty choices should be skipped

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = [chunk1, chunk2, chunk3]
        ai_service.clients["openai"] = mock_client

        chunks = list(ai_service.stream_complete("system", "user"))

        assert chunks == ["open", "ai"]
        mock_client.chat.completions.create.assert_called_once()
        # Verify stream=True was passed
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["stream"] is True

    def test_ollama_uses_same_path(self, ai_service):
        ai_service.provider = "ollama"

        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = "local"

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = [chunk]
        ai_service.clients["ollama"] = mock_client

        chunks = list(ai_service.stream_complete("system", "user"))

        assert chunks == ["local"]


class TestGHFallback:
    """Test GH CLI falls back to non-streaming."""

    def test_yields_full_response_as_single_chunk(self, ai_service):
        ai_service.provider = "gh"

        with patch.object(
            ai_service, "complete", return_value="full gh response"
        ):
            chunks = list(ai_service.stream_complete("system", "user"))

        assert chunks == ["full gh response"]
        assert len(chunks) == 1

    def test_yields_nothing_when_complete_returns_none(self, ai_service):
        ai_service.provider = "gh"

        with patch.object(ai_service, "complete", return_value=None):
            chunks = list(ai_service.stream_complete("system", "user"))

        assert chunks == []


class TestStreamDisconnect:
    """Test disconnect/error handling during streaming."""

    def test_gemini_disconnect_raises(self, ai_service):
        """Verify that a mid-stream error propagates so the TUI can catch it."""
        ai_service.provider = "gemini"

        def failing_stream(*args, **kwargs):
            yield MagicMock(text="partial ")
            raise ConnectionError("stream disconnected")

        mock_client = MagicMock()
        mock_client.models.generate_content_stream.side_effect = failing_stream

        with patch.object(ai_service, "_build_genai_client", return_value=mock_client):
            chunks = []
            with pytest.raises(ConnectionError, match="stream disconnected"):
                for chunk in ai_service.stream_complete("system", "user"):
                    chunks.append(chunk)

        # Partial content should have been captured before the error
        assert chunks == ["partial "]

    def test_openai_disconnect_preserves_partial(self, ai_service):
        """Verify partial chunks are available before error."""
        ai_service.provider = "openai"

        def failing_chunks():
            c1 = MagicMock()
            c1.choices = [MagicMock()]
            c1.choices[0].delta.content = "before_"
            yield c1
            raise TimeoutError("connection lost")

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = failing_chunks()
        ai_service.clients["openai"] = mock_client

        chunks = []
        with pytest.raises(TimeoutError):
            for chunk in ai_service.stream_complete("system", "user"):
                chunks.append(chunk)

        assert chunks == ["before_"]

    def test_unknown_provider_raises(self, ai_service):
        ai_service.provider = "nonexistent"

        with pytest.raises(ValueError, match="Unknown provider"):
            list(ai_service.stream_complete("system", "user"))
