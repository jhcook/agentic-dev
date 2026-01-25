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

import yaml
import pytest
from backend.admin.config_updater import ConfigManager, VoiceConfig, LLMConfig, STTConfig, TTSConfig, WhisperConfig

@pytest.fixture
def temp_config_file(tmp_path):
    config_file = tmp_path / "voice.yaml"
    initial_content = {
        "llm": {"provider": "gemini", "model": "gemini-pro"},
        "stt": {"provider": "deepgram", "model": "nova-2"},
        "tts": {"provider": "deepgram", "model": "aura-asteria-en"},
        "whisper": {"model_size": "tiny", "device": "auto"}
    }
    with open(config_file, "w") as f:
        yaml.dump(initial_content, f)
    return str(config_file)

def test_load_voice_config(temp_config_file):
    manager = ConfigManager(voice_config_path=temp_config_file)
    config = manager.load_voice_config()
    assert config.llm.provider == "gemini"
    assert config.stt.model == "nova-2"

def test_save_voice_config(temp_config_file):
    manager = ConfigManager(voice_config_path=temp_config_file)
    new_config = VoiceConfig(
        llm=LLMConfig(provider="openai", model="gpt-4o"),
        stt=STTConfig(provider="deepgram", model="nova-2"),
        tts=TTSConfig(provider="deepgram", model="aura-asteria-en"),
        whisper=WhisperConfig(model_size="small", device="cpu")
    )
    manager.save_voice_config(new_config)
    
    # Reload and verify
    with open(temp_config_file, "r") as f:
        data = yaml.safe_load(f)
    assert data["llm"]["provider"] == "openai"
    assert data["whisper"]["model_size"] == "small"

def test_get_schema():
    manager = ConfigManager(voice_config_path="dummy.yaml")
    schema = manager.get_schema()
    assert "properties" in schema
    assert "llm" in schema["properties"]
    assert "whisper" in schema["properties"]
