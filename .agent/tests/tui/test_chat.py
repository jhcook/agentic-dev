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
from unittest.mock import AsyncMock, MagicMock, patch
from textual.app import App
from agent.tui.chat import ChatWorkerMixin, DisconnectModal, ConfirmToolModal, process_chat_stream

class DummyApp(ChatWorkerMixin, App):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_system_prompt = ""
        self._last_user_prompt = ""
        self._last_use_tools = False
        self._partial_response = ""
        self._chat_text = []
        self._session = MagicMock()
        self._store = AsyncMock()
        self._token_budget = MagicMock()
        self._token_budget.build_context.return_value = ("sys", [])

    def _write_assistant_start(self): pass
    def _write_chunk(self, chunk): pass
    def _write_final_answer(self, text): pass
    def _update_status_bar(self): pass
    def _hide_exec_panel(self): pass
    def push_screen(self, screen, callback): pass
    
    # Mocking call_from_thread to just call directly for tests
    def call_from_thread(self, func, *args, **kwargs):
        return func(*args, **kwargs)

@pytest.mark.asyncio
async def test_chat_worker_mixin_has_methods():
    app = DummyApp()
    assert hasattr(app, "_stream_response")
    assert hasattr(app, "_do_stream")
    assert hasattr(app, "_show_disconnect_modal")

@pytest.mark.asyncio
async def test_modals_exist():
    # Verify the modals can be instantiated
    d_modal = DisconnectModal("error")
    assert d_modal is not None
    
    t_modal = ConfirmToolModal("test", "test details")
    assert t_modal is not None

@pytest.mark.asyncio
async def test_streaming_chunk_rendering():
    """Verify streaming chunk rendering delegates correctly."""
    app = DummyApp()
    with patch("agent.core.ai.ai_service.stream_complete") as mock_stream:
        # Mock the generator
        def mock_gen(*args, **kwargs):
            yield "chunk1"
            yield "chunk2"
        mock_stream.side_effect = mock_gen
        
        response = await app._do_simple_stream("sys", "user", "gemini", "model")
        assert response == "chunk1chunk2"

@pytest.mark.asyncio
async def test_disconnect_recovery_behavior():
    """Verify disconnect recovery behavior triggers the modal."""
    app = DummyApp()
    app._show_disconnect_modal = MagicMock()
    
    with patch("agent.core.ai.ai_service.stream_complete", side_effect=Exception("Connection lost")):
        response = await app._do_simple_stream("sys", "user", "gemini", "model")
        # Should return None and call disconnect modal
        assert response is None
        app._show_disconnect_modal.assert_called_once_with("Connection lost")

@pytest.mark.asyncio
async def test_log_scrubbing_logic():
    """Verify log scrubbing logic in process_chat_stream."""
    async def mock_stream():
        yield {"error": "secret_key_123"}
    
    with patch("agent.tui.chat.logger") as mock_logger, \
         patch("agent.tui.chat.scrub_sensitive_data", return_value="[REDACTED]"):
        chunks = []
        async for chunk in process_chat_stream(mock_stream()):
            chunks.append(chunk)
            
        mock_logger.error.assert_called_once()
        args, kwargs = mock_logger.error.call_args
        assert "Stream error: [REDACTED]" in args[0]
        assert kwargs["extra"]["error"] == "[REDACTED]"
