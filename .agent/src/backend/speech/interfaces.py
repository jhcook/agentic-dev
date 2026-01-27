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

from abc import abstractmethod
from typing import Protocol, runtime_checkable, AsyncGenerator

# Using Protocol for structural subtyping, which is more flexible.
@runtime_checkable
class STTProvider(Protocol):
    """
    Interface for a Speech-to-Text (STT) provider.
    """
    @abstractmethod
    async def listen(self, audio_data: bytes) -> str:
        """
        Transcribes the given audio data into text (batch mode).

        Args:
            audio_data: The raw byte content of the audio.

        Returns:
            The transcribed text.
        """
        ...
    
    async def stream(self, audio_stream: AsyncGenerator[bytes, None]) -> AsyncGenerator[str, None]:
        """
        Transcribes streaming audio data into text (streaming mode).
        
        Args:
            audio_stream: Async generator yielding audio chunks
            
        Yields:
            Transcribed text as it becomes available
        """
        # Default implementation: accumulate and use batch mode
        buffer = bytearray()
        async for chunk in audio_stream:
            buffer.extend(chunk)
        
        if buffer:
            result = await self.listen(bytes(buffer))
            if result:
                yield result

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Verifies connectivity to the STT provider.
        """
        ...

@runtime_checkable
class TTSProvider(Protocol):
    """
    Interface for a Text-to-Speech (TTS) provider.
    """
    @abstractmethod
    async def speak(self, text: str) -> bytes:
        """
        Synthesizes the given text into audio.

        Args:
            text: The text to be synthesized.

        Returns:
            The raw byte content of the generated audio.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Verifies connectivity to the TTS provider.
        """
        ...

class DisabledSTT:
    """Fallback STT provider that does nothing."""
    async def listen(self, audio_data: bytes, **kwargs) -> str:
        return ""
    
    async def stream(self, audio_stream: AsyncGenerator[bytes, None]) -> AsyncGenerator[str, None]:
        if False: yield "" # Make it an async generator
        return

    async def health_check(self) -> bool:
        return False

class DisabledTTS:
    """Fallback TTS provider that does nothing."""
    async def speak(self, text: str) -> bytes:
        return b""

    async def health_check(self) -> bool:
        return False
