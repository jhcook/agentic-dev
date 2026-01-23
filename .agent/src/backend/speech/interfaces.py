from abc import abstractmethod
from typing import Protocol, runtime_checkable

# Using Protocol for structural subtyping, which is more flexible.
@runtime_checkable
class STTProvider(Protocol):
    """
    Interface for a Speech-to-Text (STT) provider.
    """
    @abstractmethod
    async def listen(self, audio_data: bytes) -> str:
        """
        Transcribes the given audio data into text.

        Args:
            audio_data: The raw byte content of the audio.

        Returns:
            The transcribed text.
        """
        ...

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
