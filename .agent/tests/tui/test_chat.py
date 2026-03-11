# Copyright 2026 Justin Cook
"""Unit tests for the TUI chat module."""

import pytest
from unittest.mock import AsyncMock, patch
from agent.tui.chat import process_chat_stream, DisconnectModal, resolve_provider

@pytest.mark.asyncio
async def test_process_chat_stream_success():
    """Verify that streaming chunks flow correctly."""
    async def mock_stream():
        """Mock a successful stream of chat chunks."""
        yield {"choices": [{"delta": {"content": "Hello"}}]}
        yield {"choices": [{"delta": {"content": " world"}}]}

    results = []
    async for chunk in process_chat_stream(mock_stream()):
        results.append(chunk)

    assert results == ["Hello", " world"]

@pytest.mark.asyncio
async def test_process_chat_stream_error():
    """Verify that connection drops and API errors are handled gracefully."""
    async def mock_stream():
        """Mock an errored stream."""
        yield {"error": "Connection drop"}

    with patch("agent.tui.chat.logger") as mock_logger:
        results = []
        async for chunk in process_chat_stream(mock_stream()):
            results.append(chunk)

        assert results == ["\n[Error: Connection drop]"]
        mock_logger.error.assert_called()

def test_resolve_provider():
    """Verify resolve_provider handoff works."""
    with patch("agent.tui.chat.ai_service") as mock_ai_service:
        resolve_provider("test_provider")
        mock_ai_service.get_provider.assert_called_with("test_provider")
