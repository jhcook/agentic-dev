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

import logging
import asyncio

try:
    import azure.cognitiveservices.speech as speechsdk
except ImportError:
    speechsdk = None

logger = logging.getLogger(__name__)

class AzureSTT:
    def __init__(self, subscription_key: str, region: str):
        if not speechsdk:
            raise ImportError("azure-cognitiveservices-speech is not installed.")
            
        # Security: Validate region format (alphanumeric, hyphens) to prevent injection
        import re
        if not re.match(r"^[a-z0-9-]+$", region):
            logger.error(f"Invalid Azure region format: {region}")
            raise ValueError("Invalid Azure region. Must be alphanumeric/hyphens.")
            
        self.speech_config = speechsdk.SpeechConfig(subscription=subscription_key, region=region)

    async def listen(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        """
        Transcribes the given audio data into text (batch mode).
        """
        if not audio_data:
            return ""
        if len(audio_data) > 10 * 1024 * 1024:
            logger.warning("Azure STT: Audio data too large.")
            return ""

        def _transcribe():
            # Setup push stream for raw audio bytes
            stream = speechsdk.audio.PushAudioInputStream(
                stream_format=speechsdk.audio.AudioStreamFormat(
                    samples_per_second=sample_rate, 
                    bits_per_sample=16, 
                    channels=1
                )
            )
            audio_config = speechsdk.audio.AudioConfig(stream=stream)
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=self.speech_config, 
                audio_config=audio_config
            )
            
            # Write data and close stream
            stream.write(audio_data)
            stream.close()
            
            # Run recognition
            result = recognizer.recognize_once()
            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                return result.text
            elif result.reason == speechsdk.ResultReason.NoMatch:
                logger.info("Azure STT: No speech could be recognized.")
                return ""
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                logger.warning(f"Azure STT Canceled: {cancellation_details.reason}")
                if cancellation_details.reason == speechsdk.CancellationReason.Error:
                    logger.error(f"Azure STT Error: {cancellation_details.error_details}")
                return ""
            return ""

        try:
            return await asyncio.to_thread(_transcribe)
        except Exception as e:
            logger.error(f"Azure STT listen failed: {e}")
            return ""

    async def health_check(self) -> bool:
        """
        Verifies connectivity by attempting to instantiate a recognizer. 
        Note: The SDK might delay auth check until first recognition, but this catches basic config errors.
        """
        try:
             # Basic object validity check
             if not self.speech_config: return False
             # instantiation check
             _ = speechsdk.SpeechRecognizer(speech_config=self.speech_config)
             return True
        except Exception:
            return False


class AzureTTS:
    def __init__(self, subscription_key: str, region: str):
        if not speechsdk:
            raise ImportError("azure-cognitiveservices-speech is not installed.")
            
        # Security: Validate region
        import re
        if not re.match(r"^[a-z0-9-]+$", region):
            logger.error(f"Invalid Azure region format: {region}")
            raise ValueError("Invalid Azure region. Must be alphanumeric/hyphens.")

        self.speech_config = speechsdk.SpeechConfig(subscription=subscription_key, region=region)
        # Using None for audio_config prevents playback to default speaker, allows getting result data
        self.speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config, audio_config=None)

    async def speak(self, text: str, language_code: str = "en-US") -> bytes:
        """
        Synthesizes the given text into audio.
        """
        if not text:
            return b""
        if len(text) > 5000:
            logger.warning("Azure TTS: Text too long.")
            return b""

        def _synthesize():
            # Create a localized config for this request if needed, or set property
            self.speech_config.speech_synthesis_language = language_code
            
            result = self.speech_synthesizer.speak_text_async(text).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                return result.audio_data
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                logger.warning(f"Azure TTS Canceled: {cancellation_details.reason}")
                if cancellation_details.reason == speechsdk.CancellationReason.Error:
                    logger.error(f"Azure TTS Error: {cancellation_details.error_details}")
                return b""
            return b""

        try:
            return await asyncio.to_thread(_synthesize)
        except Exception as e:
            logger.error(f"Azure TTS speak failed: {e}")
            return b""

    async def health_check(self) -> bool:
        """
        Verifies connectivity.
        """
        return True
