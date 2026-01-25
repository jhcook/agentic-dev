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

import asyncio
import logging
import time
import json
from pathlib import Path
from typing import AsyncGenerator, Optional, List

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.sqlite import SqliteSaver
from opentelemetry import trace
from prometheus_client import Counter, Histogram

from backend.speech.factory import get_voice_providers
from agent.core.config import config
from agent.core.secrets import get_secret
from backend.admin.logger import log_bus
from backend.voice.tools import lookup_documentation

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

# Metrics
AGENT_REQUESTS = Counter(
    "voice_agent_requests_total",
    "Total agent requests",
    ["model", "status"]
)

AGENT_LATENCY = Histogram(
    "voice_agent_response_duration_seconds",
    "Agent response latency",
    ["model"]
)

AGENT_TOKENS = Counter(
    "voice_agent_token_usage_total",
    "Token usage",
    ["model", "type"]
)

def load_voice_system_prompt() -> str:
    """Load voice system prompt from etc/prompts/voice_system_prompt.txt."""
    try:
        from agent.core.config import config
        prompt_path = config.etc_dir / "prompts" / "voice_system_prompt.txt"
        if prompt_path.exists():
            return prompt_path.read_text().strip()
    except Exception as e:
        logger.warning(f"Failed to load system prompt: {e}")
    
    # Fallback
    return "You are a helpful voice assistant. Keep answers concise for speech."


def _get_voice_config() -> dict:
    """Load voice configuration from voice.yaml."""
    try:
        config_path = config.etc_dir / "voice.yaml"
        if config_path.exists():
            return config.load_yaml(config_path)
    except Exception as e:
        logger.warning(f"Failed to load voice.yaml: {e}")
    return {}


def _create_llm():
    """
    Factory for LLM provider (configurable via agent config).
    """
    voice_config = _get_voice_config()
    
    # Get provider and model from config, default to openai/gpt-4o-mini
    provider = config.get_value(voice_config, "llm.provider") or "openai"
    model_name = config.get_value(voice_config, "llm.model") 
    
    provider = provider.lower()
    
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        api_key = get_secret("api_key", service="openai")
        model = model_name or "gpt-4o-mini"
        return ChatOpenAI(
            api_key=api_key,
            model=model,
            streaming=True,
            temperature=0.7
        )
    
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        api_key = get_secret("api_key", service="anthropic")
        model = model_name or "claude-3-5-sonnet-20241022"
        return ChatAnthropic(
            api_key=api_key,
            model=model,
            streaming=True,
            temperature=0.7
        )
    
    elif provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        api_key = get_secret("api_key", service="gemini")
        model = model_name or "gemini-2.0-flash-exp"
        return ChatGoogleGenerativeAI(
            google_api_key=api_key,
            model=model,
            streaming=True,
            temperature=0.7
        )
        
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}. Use 'openai', 'anthropic', or 'gemini'.")


class VoiceOrchestrator:
    """Orchestrates voice interaction flow with LangGraph agent."""
    
    def __init__(self, session_id: str):
        """
        Initialize VoiceOrchestrator with LangGraph conversational agent.
        
        Args:
            session_id: Unique session identifier for conversation tracking
        """
        self.session_id = session_id
        self.stt, self.tts = get_voice_providers()
        
        # Initialize LLM (configurable via env)
        llm = _create_llm()
        
        # Configure tools
        tools = [lookup_documentation]
        
        # Persistence: SqliteSaver
        # Ensure directory exists
        storage_dir = Path(".agent/storage")
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        # We need a connection per session or a shared one?
        # SqliteSaver.from_conn_string handles connections contextually usually.
        # But we need to maintain the connection if we pass it instance.
        self.db_path = storage_dir / "voice.sqlite"
        self.conn = SqliteSaver.from_conn_string(str(self.db_path))
        
        # Create agent with system prompt
        self.agent = create_react_agent(
            llm, 
            tools,
            prompt=load_voice_system_prompt(),
            checkpointer=self.conn
        )
        
        # State
        self.is_speaking = asyncio.Event()
        self.is_thinking = False
        
        # Audio accumulation buffer for STT (file-based API needs larger chunks)
        self.audio_buffer = bytearray()
        self.buffer_duration_ms = 1500  # 1.5 seconds
        self.sample_rate = 16000
        self.bytes_per_sample = 2  # Int16
        self.target_buffer_size = int(
            (self.buffer_duration_ms / 1000) * self.sample_rate * self.bytes_per_sample
        )  # ~48KB for 1.5s at 16kHz
        
        # VAD
        try:
            from backend.voice.vad import VADProcessor
            self.vad = VADProcessor()
        except Exception as e:
            logger.warning(f"VAD initialization failed: {e}. Interrupts disabled.")
            self.vad = None
        
        # Callback for events (injected by router)
        self.on_event = None
        
    def _sanitize_user_input(self, text: str) -> str:
        # ... (unchanged)
        return text # Abbreviated for tool

    # ... (process_audio start unchanged)

            logger.info(
                "User input received",
                extra={"session_id": self.session_id, "length": len(text_input), "text": text_input}
            )
            
            # EMIT USER EVENT
            if self.on_event:
                self.on_event("transcript.user", {"text": text_input})

            # ... (buffer logic)
            
            # ... (_invoke_agent)
            
                if hasattr(msg_chunk, 'content') and msg_chunk.content:
                     # Filter empty strings
                     content = str(msg_chunk.content)
                     if content:
                        first_token_received = True
                        AGENT_TOKENS.labels(model=self.model_name, type="completion").inc(1)
                        
                        # EMIT AGENT EVENT
                        if self.on_event:
                            self.on_event("transcript.agent", {"text": content})
                            
                        yield content
                        
                # TODO: Catch Tool calls for logging/transcript?
                # LangGraph 0.1+ yields tool calls in chunks too.
            
            AGENT_REQUESTS.labels(model=self.model_name, status=status).inc()
            
        except Exception as e:
            status = "error"
            AGENT_REQUESTS.labels(model=self.model_name, status=status).inc()
            logger.error(
                f"Agent invocation failed: {e}",
                extra={"session_id": self.session_id, "error": str(e)}
            )
            # Fallback
            yield "I'm sorry, I encountered an error."
        finally:
            AGENT_LATENCY.labels(model=self.model_name).observe(time.time() - start)
