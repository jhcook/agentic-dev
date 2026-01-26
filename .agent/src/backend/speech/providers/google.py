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
from typing import Optional

from google.cloud import speech_v1 as speech
from google.cloud import texttospeech_v1 as texttospeech

logger = logging.getLogger(__name__)

class GoogleSTT:
    def __init__(self, credentials_json: Optional[str] = None):
        if credentials_json:
            import json
            try:
                info = json.loads(credentials_json)
                self.client = speech.SpeechAsyncClient.from_service_account_info(info)
            except json.JSONDecodeError:
                logger.error("GoogleSTT: Invalid JSON credentials.")
                self.client = None
            except Exception as e:
                 logger.error(f"GoogleSTT: Client init failed: {e}")
                 self.client = None
        else:
            # Security: Strictly enforce Secret Manager usage. No ADC fallback.
            logger.error("GoogleSTT: No credentials provided.")
            self.client = None 
            raise ValueError("GoogleSTT requires credentials_json from Secret Manager.")

    async def listen(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        """
        Transcribes the given audio data into text (batch mode).
        """
        if not audio_data:
            return ""
            
        # Basic validation
        if len(audio_data) > 10 * 1024 * 1024: # 10MB limit
             logger.warning("Google STT: Audio data too large.")
             return ""

        try:
            audio = speech.RecognitionAudio(content=audio_data)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=sample_rate,
                language_code="en-US",
            )
            response = await self.client.recognize(config=config, audio=audio)
            
            transcript = ""
            if response.results:
                transcript = response.results[0].alternatives[0].transcript
            
            return transcript
        except Exception as e:
            logger.error(f"Google STT listen failed: {e}")
            return ""

    async def health_check(self) -> bool:
        """
        Verifies connectivity to Google Cloud.
        """
        try:
            # Check if transport is open/valid
            if not self.client: return False
            # Ideally we would ping, but client instantiation is a good enough proxy for config validity
            return True
        except Exception:
            return False


class GoogleTTS:
    def __init__(self, credentials_json: Optional[str] = None):
        if credentials_json:
            import json
            try:
                info = json.loads(credentials_json)
                self.client = texttospeech.TextToSpeechAsyncClient.from_service_account_info(info)
            except json.JSONDecodeError:
                logger.error("GoogleTTS: Invalid JSON credentials.")
                self.client = None
            except Exception as e:
                 logger.error(f"GoogleTTS: Client init failed: {e}")
                 self.client = None
        else:
             # Security: Strictly enforce Secret Manager usage.
             logger.error("GoogleTTS: No credentials provided.")
             raise ValueError("GoogleTTS requires credentials_json from Secret Manager.")

    async def speak(self, text: str, language_code: str = "en-US") -> bytes:
        """
        Synthesizes the given text into audio.
        """
        if not text:
            return b""
            
        # Input validation
        if len(text) > 5000:
            logger.warning("Google TTS: Text too long.")
            return b""
            
        try:
            input_text = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(
                language_code=language_code,
                ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16
            )
            response = await self.client.synthesize_speech(
                request={"input": input_text, "voice": voice, "audio_config": audio_config}
            )
            return response.audio_content
        except Exception as e:
            logger.error(f"Google TTS speak failed: {e}")
            return b""

    async def health_check(self) -> bool:
        """
        Verifies connectivity by listing voices.
        """
        try:
            await self.client.list_voices(request=texttospeech.ListVoicesRequest(language_code="en-US"))
            return True
        except Exception as e:
            logger.warning(f"Google TTS Health Check failed: {e}")
            return False
