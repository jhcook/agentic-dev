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
    async def listen(self, audio_data: bytes) -> str:
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
