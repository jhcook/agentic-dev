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

import os
import yaml
import logging
from typing import Dict, Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class LLMConfig(BaseModel):
    provider: str = Field(..., description="LLM provider name (e.g., gemini, openai)")
    model: str = Field(..., description="Model ID to use")

class STTConfig(BaseModel):
    provider: str = Field(..., description="STT provider (deepgram, whisper)")
    model: str = Field(..., description="Model name")

class TTSConfig(BaseModel):
    provider: str = Field(..., description="TTS provider (deepgram, kokoro)")
    model: str = Field(..., description="Voice model name")

class WhisperConfig(BaseModel):
    model_size: str = Field("tiny", description="Whisper model size")
    device: str = Field("auto", description="Execution device (cpu, cuda, auto)")

class VoiceConfig(BaseModel):
    llm: LLMConfig
    stt: STTConfig
    tts: TTSConfig
    whisper: WhisperConfig

class ConfigManager:
    """Manages YAML configuration with Pydantic validation and atomic writes."""
    
    def __init__(self, voice_config_path: str):
        self.voice_config_path = voice_config_path

    def load_voice_config(self) -> VoiceConfig:
        """Loads and validates voice.yaml."""
        if not os.path.exists(self.voice_config_path):
            raise FileNotFoundError(f"Config file not found: {self.voice_config_path}")
            
        with open(self.voice_config_path, 'r') as f:
            data = yaml.safe_load(f)
            
        return VoiceConfig(**data)

    def save_voice_config(self, config: VoiceConfig):
        """Atomically saves VoiceConfig to YAML."""
        temp_path = f"{self.voice_config_path}.tmp"
        try:
            with open(temp_path, 'w') as f:
                # Convert to dict and dump to YAML
                yaml.dump(config.model_dump(), f, default_flow_style=False)
            
            # Atomic replace
            os.replace(temp_path, self.voice_config_path)
            logger.info(f"Successfully updated {self.voice_config_path}")
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            logger.error(f"Failed to save config: {e}")
            raise

    def get_schema(self) -> Dict[str, Any]:
        """Returns JSON schema for VoiceConfig to drive frontend forms."""
        return VoiceConfig.model_json_schema()
