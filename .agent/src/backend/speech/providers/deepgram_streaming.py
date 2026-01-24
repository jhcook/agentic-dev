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

"""Deepgram streaming WebSocket STT provider."""

import asyncio
import logging
from typing import AsyncGenerator
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions

from backend.speech.interfaces import STTProvider

logger = logging.getLogger(__name__)


class DeepgramStreamingSTT(STTProvider):
    """Deepgram streaming WebSocket implementation for real-time STT."""
    
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Deepgram API key is required")
        self.api_key = api_key
        self.client = DeepgramClient(api_key=api_key)
        self.provider_name = "deepgram_streaming"
    
    async def listen(self, audio_data: bytes) -> str:
        """Batch mode: accumulate and transcribe (fallback)."""
        from backend.speech.audio_utils import pcm_to_wav
        
        # Convert to WAV and use file API as fallback
        wav_data = pcm_to_wav(audio_data, sample_rate=16000, channels=1, sample_width=2)
        
        response = await asyncio.to_thread(
            self.client.listen.v1.media.transcribe_file,
            request=wav_data,
            model="nova-2",
            smart_format=True
        )
        
        return response.results.channels[0].alternatives[0].transcript
    
    async def stream(self, audio_stream: AsyncGenerator[bytes, None]) -> AsyncGenerator[str, None]:
        """
        Streaming mode: real-time transcription via WebSocket.
        
        Args:
            audio_stream: Async generator yielding raw PCM audio chunks (Int16, 16kHz)
            
        Yields:
            Transcribed text as it becomes available
        """
        transcript_queue = asyncio.Queue()
        connection_closed = asyncio.Event()
        
        # Configure streaming options
        options = LiveOptions(
            model="nova-2",
            language="en-US",
            smart_format=True,
            encoding="linear16",
            sample_rate=16000,
            channels=1,
            interim_results=False,  # Only final results
        )
        
        # Create WebSocket connection
        dg_connection = self.client.listen.live.v("1")
        
        # Set up event handlers
        def on_message(self, result, **kwargs):
            sentence = result.channel.alternatives[0].transcript
            if sentence.strip():
                asyncio.create_task(transcript_queue.put(sentence))
        
        def on_error(self, error, **kwargs):
            logger.error(f"Deepgram streaming error: {error}")
            asyncio.create_task(transcript_queue.put(None))  # Signal error
        
        def on_close(self, **kwargs):
            logger.info("Deepgram streaming connection closed")
            connection_closed.set()
            asyncio.create_task(transcript_queue.put(None))  # Signal completion
        
        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        dg_connection.on(LiveTranscriptionEvents.Error, on_error)
        dg_connection.on(LiveTranscriptionEvents.Close, on_close)
        
        # Start connection
        if not await asyncio.to_thread(dg_connection.start, options):
            raise RuntimeError("Failed to start Deepgram streaming connection")
        
        logger.info("Deepgram streaming connection established")
        
        # Stream audio chunks to Deepgram
        async def send_audio():
            try:
                async for chunk in audio_stream:
                    if connection_closed.is_set():
                        break
                    dg_connection.send(chunk)
                    await asyncio.sleep(0)  # Yield control
                
                # Signal end of audio
                dg_connection.finish()
            except Exception as e:
                logger.error(f"Error sending audio to Deepgram: {e}")
                dg_connection.finish()
        
        # Start sending audio in background
        send_task = asyncio.create_task(send_audio())
        
        # Yield transcripts as they arrive
        try:
            while True:
                transcript = await transcript_queue.get()
                if transcript is None:  # Completion or error signal
                    break
                yield transcript
        finally:
            # Cleanup
            if not send_task.done():
                send_task.cancel()
            try:
                await send_task
            except asyncio.CancelledError:
                pass
    
    async def health_check(self) -> bool:
        """Check if API key is valid."""
        return True  # Deepgram doesn't have a dedicated ping endpoint
