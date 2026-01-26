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
import asyncio
import time
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from backend.main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_interrupt_flow(client):
    # Mock Orchestrator to simulate barge-in
    with patch("backend.routers.voice.VoiceOrchestrator") as check_mock:
        mock_orch = MagicMock()
        check_mock.return_value = mock_orch
        
        # Setup: is_speaking event is set => Agent IS speaking
        mock_orch.is_speaking.is_set.return_value = True
        
        with client.websocket_connect("/ws/voice") as websocket:
            websocket.send_bytes(b"dummy audio")
            # Wait for router to process
            time.sleep(0.2)
            # Verify push_audio was called by the router
            mock_orch.push_audio.assert_called_with(b"dummy audio")

def test_no_interrupt_when_silent(client):
    with patch("backend.routers.voice.VoiceOrchestrator") as check_mock:
        mock_orch = MagicMock()
        check_mock.return_value = mock_orch
        
        mock_orch.is_speaking.is_set.return_value = True
        
        with client.websocket_connect("/ws/voice") as websocket:
            websocket.send_bytes(b"silence")
            time.sleep(0.2)
            mock_orch.push_audio.assert_called_with(b"silence")
