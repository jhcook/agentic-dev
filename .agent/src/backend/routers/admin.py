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

from fastapi import APIRouter, HTTPException
from backend.admin.config_updater import ConfigManager, VoiceConfig
import os

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Resolve path to etc/voice.yaml relative to this file
# Current file is in .agent/src/backend/routers/admin.py
# target is .agent/etc/voice.yaml
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
VOICE_CONFIG_PATH = os.path.join(BASE_DIR, "etc", "voice.yaml")

manager = ConfigManager(voice_config_path=VOICE_CONFIG_PATH)
PROMPTS_DIR = os.path.join(BASE_DIR, "etc", "prompts")

@router.get("/health")
async def health_check():
    """Simple health check for the Admin API."""
    return {"status": "ok", "service": "agent-admin"}

@router.get("/config/voice")
async def get_voice_config():
    """Returns the current voice configuration."""
    try:
        return manager.load_voice_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/config/schema")
async def get_config_schema():
    """Returns the JSON schema for VoiceConfig."""
    return manager.get_schema()

@router.post("/config/voice")
async def update_voice_config(config: VoiceConfig):
    """Updates the voice configuration atomically."""
    try:
        manager.save_voice_config(config)
        return {"message": "Configuration updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/prompts")
async def list_prompts():
    """Lists available system prompts."""
    if not os.path.exists(PROMPTS_DIR):
        return []
    return [f for f in os.listdir(PROMPTS_DIR) if f.endswith(".txt")]

@router.get("/prompts/{filename}")
async def get_prompt(filename: str):
    """Reads a specific system prompt."""
    path = os.path.join(PROMPTS_DIR, filename)
    if not os.path.exists(path) or ".." in filename:
        raise HTTPException(status_code=404, detail="Prompt not found")
    with open(path, "r") as f:
        return {"filename": filename, "content": f.read()}

@router.post("/prompts/{filename}")
async def update_prompt(filename: str, data: dict):
    """Updates a system prompt atomically."""
    path = os.path.join(PROMPTS_DIR, filename)
    if ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    content = data.get("content", "")
    temp_path = f"{path}.tmp"
    try:
        with open(temp_path, "w") as f:
            f.write(content)
        os.replace(temp_path, path)
        return {"message": "Prompt updated successfully"}
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=str(e))
