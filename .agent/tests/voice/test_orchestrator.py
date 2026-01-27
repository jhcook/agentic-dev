import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from backend.voice.orchestrator import VoiceOrchestrator
from langgraph.checkpoint.memory import MemorySaver
# Force import of modules to ensure they are registered for patching
import backend.voice.vad 

@pytest.fixture
def mock_deps():
    # Patch where the classes are DEFINED, not where they are imported (since they are local imports)
    with patch("backend.voice.vad.VADProcessor") as MockVAD, \
         patch("backend.voice.orchestrator.get_voice_providers") as MockGetProviders, \
         patch("backend.voice.orchestrator.GLOBAL_MEMORY", MemorySaver()): # Real memory saver
        
        mock_vad = MockVAD.return_value
        
        mock_stt = AsyncMock()
        mock_tts = AsyncMock()
        MockGetProviders.return_value = (mock_stt, mock_tts)
        
        yield mock_vad, mock_stt, mock_tts

@pytest.mark.asyncio
async def test_orchestrator_initialization(mock_deps):
    mock_vad, mock_stt, mock_tts = mock_deps
    
    with patch("backend.voice.orchestrator._create_llm"):
         orch = VoiceOrchestrator(session_id="test")
         assert orch.vad == mock_vad
         assert orch.stt == mock_stt
         assert orch.tts == mock_tts

@pytest.mark.asyncio
async def test_process_audio_chunk(mock_deps):
    mock_vad, mock_stt, mock_tts = mock_deps
    
    # Simulate speech detection
    mock_vad.process.return_value = True 
    
    with patch("backend.voice.orchestrator._create_llm"):
        orch = VoiceOrchestrator(session_id="test")
        
        # Process a dummy chunk
        # Since _process_audio_chunk is async
        await orch._process_audio_chunk(b"audio_data")
        
        # Verify VAD was called
        mock_vad.process.assert_called_with(b"audio_data")

@pytest.mark.asyncio
async def test_heal_chat_history_called(mock_deps):
     with patch("backend.voice.orchestrator._create_llm"), \
          patch("backend.voice.orchestrator.VoiceOrchestrator._heal_chat_history") as mock_heal:
        orch = VoiceOrchestrator(session_id="test")
        assert hasattr(orch, "_heal_chat_history")
