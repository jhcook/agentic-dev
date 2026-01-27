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
import re
from datetime import datetime, timedelta
import json

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import ToolMessage, AIMessage
from opentelemetry import trace
from prometheus_client import Counter, Histogram

from backend.speech.factory import get_voice_providers
from agent.core.config import config
from agent.core.secrets import get_secret

logger = logging.getLogger(__name__)
# Explicitly add handler for backend logging to capture TRACEs in admin_backend.log
if not logger.handlers:
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(sh)
    logger.setLevel(logging.INFO)

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

def _load_system_prompt() -> str:
    """Load the voice system prompt from the etc/prompts directory."""
    try:
        prompt_path = config.etc_dir / "prompts" / "voice_system_prompt.txt"
        if prompt_path.exists():
            return prompt_path.read_text().strip()
    except Exception as e:
        logger.warning(f"Failed to load voice_system_prompt.txt: {e}")
    
    # Fallback to a basic prompt if file loading fails
    return "You are a helpful voice assistant. Be concise."

VOICE_SYSTEM_PROMPT = _load_system_prompt()

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
    
    Configuration comes from:
    1. .agent/etc/voice.yaml (llm.provider, llm.model)
    2. Defaults (openai, gpt-4o-mini)
    
    Returns:
        Configured LangChain chat model
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


# Global memory to persist across WebSocket reconnections (but reset on process restart)
GLOBAL_MEMORY = MemorySaver()


async def get_chat_history(session_id: str) -> list[dict]:
    """
    Retrieve chat history for a session from Global Memory.
    Returns list of {"role": "user"|"assistant", "text": "..."}
    """
    if not GLOBAL_MEMORY:
        return []
        
    config = {"configurable": {"thread_id": session_id}}
    # MemorySaver .get() returns a StateSnapshot
    # We need to access .values['messages']
    
    # Since this is synchronous MemorySaver (or async?), wait, LangGraph AsyncSqliteSaver is async.
    # MemorySaver is usually sync?
    # Actually, GLOBAL_MEMORY = MemorySaver() is synchronous in LangGraph default.
    # But let's assume async access pattern for future-proofing or if it supports aget.
    
    # MemorySaver has .get(config) -> StateSnapshot
    snapshot = GLOBAL_MEMORY.get(config)
    if not snapshot:
        return []
        
    # Correctly access messages from CheckpointTuple
    # snapshot is a CheckpointTuple with .checkpoint (dict)
    try:
        messages = snapshot.checkpoint["channel_values"].get("messages", [])
    except (AttributeError, KeyError):
        # Fallback for alternative structures
        try:
            messages = snapshot.values.get("messages", [])
        except (AttributeError, TypeError):
            messages = []
            
    history = []
    
    for msg in messages:
        # Convert LangChain/LangGraph messages to our format
        role = "user" if msg.type == "human" else "assistant"
        if msg.type == "ai": role = "assistant"
        
        # Skip system messages or tool calls if we only want chat
        if msg.type not in ["human", "ai"]:
            continue
            
        # Robust content handling (handle lists/multimodal)
        content = msg.content
        if isinstance(content, list):
            # Extract text parts
            text_parts = []
            for part in content:
                if isinstance(part, str):
                    text_parts.append(part)
                elif isinstance(part, dict) and "text" in part:
                    text_parts.append(part["text"])
            text = " ".join(text_parts)
        else:
            text = str(content) if content is not None else ""
            
        history.append({
            "role": role,
            "text": text
        })
        
    return history

def _persist_session_history(session_id: str, history: list[dict]):
    """Persist chat history to disk for review."""
    try:
        storage_dir = config.agent_dir / "storage" / "voice_sessions"
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = storage_dir / f"{session_id}.json"
        with open(file_path, 'w') as f:
            json.dump({
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat(),
                "history": history
            }, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to persist session {session_id}: {e}")

def strip_markdown_for_tts(text: str) -> str:
    """Removes markdown elements and technical junk that should not be spoken."""
    # 1. Remove triple-backtick code blocks and their content
    text = re.sub(r'```[\s\S]*?```', ' ', text)
    # 2. Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # 3. Remove URLs
    text = re.sub(r'http\S+', '', text)
    # 4. Remove internal markdown syntax but keep words
    # Remove markers like [text](link) -> text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # 5. Remove bold/italic markers
    text = text.replace('**', '').replace('__', '').replace('*', '').replace('_', '')
    # 6. Remove inline code markers
    text = text.replace('`', '')
    # 7. Remove bullets and headers
    text = re.sub(r'^\s*[#\-\+\*]+\s+', ' ', text, flags=re.MULTILINE)
    # 8. Remove common technical symbols that cause artifacts in TTS
    # (brackets, braces, pipes, repeated dashes/equals)
    text = re.sub(r'[\[\]\{\}\|\\]', ' ', text)
    text = re.sub(r'[-=]{2,}', ' ', text)
    # 9. Collapse multiple newlines/spaces into single spaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

class VoiceOrchestrator:
    """Orchestrates voice interaction flow with LangGraph agent using Sequential Queueing."""
    
    def __init__(self, session_id: str):
        """
        Initialize VoiceOrchestrator with LangGraph conversational agent.
        
        Args:
            session_id: Unique session identifier for conversation tracking
        """
        self.session_id = session_id
        self.last_agent_text = "" # For echo suppression
        self.stt, self.tts = get_voice_providers()
        
        # Initialize LLM (configurable via env)
        llm = _create_llm()
        
        # Configure tools
        from backend.voice.tools.registry import get_all_tools
        tools = get_all_tools()
        
        # Use global checkpointer
        self.checkpointer = GLOBAL_MEMORY
        
        # Create agent with system prompt and persistence
        self.agent = create_react_agent(
            llm, 
            tools,
            prompt=VOICE_SYSTEM_PROMPT,  # LangGraph system prompt
            checkpointer=self.checkpointer
        )
        
        # Injected dependencies
        self.on_event = None
        self.output_queue: Optional[asyncio.Queue] = None
        
        # Load voice settings
        voice_config_path = config.etc_dir / "voice.yaml"
        voice_config = config.load_yaml(voice_config_path) if voice_config_path.exists() else {}
        
        # Queues & Tasks
        self.input_queue = asyncio.Queue()
        self.worker_task: Optional[asyncio.Task] = None
        
        # State
        self.is_speaking = asyncio.Event()
        self.is_running = False
        
        # Audio accumulator
        self.audio_buffer = bytearray()
        
        # Generation Tracking
        self.current_generation_id = 0
        self.pipeline_task: Optional[asyncio.Task] = None
        
        # VAD Endpointing State
        self.speech_active = False          # Has user started speaking?
        self.silence_start_time = None      # When did silence begin?
        self.last_speech_time = time.time() # Last time speech was detected
        
        # Tuning Parameters
        self.SILENCE_THRESHOLD = config.get_value(voice_config, "vad.silence_threshold") or 0.7
        self.MAX_RECORDING_DURATION = 15.0  # Max seconds before forcing process
        self.MIN_SPEECH_DURATION = 0.1      # Min speech to trigger 'active' state
        
        
        # Telemetry info
        self.bytes_per_sample = 2
        self.sample_rate = 16000
        
        # VAD
        try:
            from backend.voice.vad import VADProcessor
            v_agg = config.get_value(voice_config, "vad.aggressiveness")
            if v_agg is None: v_agg = 1
            # Ensure int for webrtcvad
            v_threshold = config.get_value(voice_config, "vad.threshold")
            if v_threshold is None: v_threshold = 0.5
            
            # VAD Initialization with optional Autotuning
            v_autotune = config.get_value(voice_config, "vad.autotune") or False
            
            self.vad = VADProcessor(
                aggressiveness=int(float(v_agg)), 
                sample_rate=self.sample_rate,
                threshold=float(v_threshold),
                autotune=bool(v_autotune)
            )
        except Exception as e:
            logger.warning(f"VAD initialization failed: {e}. Interrupts disabled.")
            self.vad = None
        
        # Get model and provider names for metrics/telemetry
        voice_config = _get_voice_config()
        self.model_name = config.get_value(voice_config, "llm.model") or "gpt-4o-mini"
        
        # Resolve STT provider name for telemetry (Env > Config > Default)
        import os
        self.stt_provider_name = os.getenv(
            "VOICE_STT_PROVIDER", 
            config.get_value(voice_config, "stt.provider") or "deepgram"
        ).lower()

    def run_background(self, output_queue: asyncio.Queue):
        """Start the background worker loop."""
        self.output_queue = output_queue
        self.is_running = True
        self.worker_task = asyncio.create_task(self._process_loop())
        logger.info(f"Orchestrator worker started for session {self.session_id}")

    def stop(self):
        """Stop the background worker."""
        self.is_running = False
        if self.worker_task:
            self.worker_task.cancel()
        if self.pipeline_task:
            self.pipeline_task.cancel()
        logger.info(f"Orchestrator worker stopped for session {self.session_id}")

    def push_audio(self, audio_chunk: bytes):
        """Push raw audio chunk to the input queue for sequential processing."""
        self.input_queue.put_nowait(audio_chunk)

    async def _process_loop(self):
        """Infinite loop consuming audio packets and running the state machine."""
        try:
            while self.is_running:
                # 1. Get next packet
                audio_chunk = await self.input_queue.get()
                if audio_chunk is None: break # Sentinel
                
                # 2. Update State machine
                await self._process_audio_chunk(audio_chunk)
                
                self.input_queue.task_done()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Orchestrator loop error: {e}", exc_info=True)

    async def _process_audio_chunk(self, audio_chunk: bytes):
        """Internal VAD Logic - Decides when to trigger the pipeline."""
        now = time.time()
        
        
        # Trace first packet
        if len(self.audio_buffer) == 0:
             logger.debug(f"AUDIO_TRACE[{self.session_id}]: First packet. Size={len(audio_chunk)}")
             
        self.audio_buffer.extend(audio_chunk)
        
        # 1. Run VAD (Unified Gate & Engine)
        has_speech = self.process_vad(audio_chunk)
        
        # 2. Update State Machine & Handle Barge-in
        if has_speech:
            # Calculate RMS for trace logging only when speech is suspected
            import struct
            import math
            count = len(audio_chunk) / 2
            format = "%dh" % count
            shorts = struct.unpack(format, audio_chunk)
            sum_squares = sum(s*s for s in shorts)
            rms = math.sqrt(sum_squares / count) if count > 0 else 0

            if not self.speech_active:
                 logger.debug(f"VAD_TRACE[{self.session_id}]: Speech START. Vol={rms:.2f}")
                 
            # BARGE-IN: If user speaks while we are still generating/speaking
            if self.is_speaking.is_set():
                logger.info(f"BARGE_IN_DETECTED[{self.session_id}]: User speech detected (RMS={rms:.0f}) during agent output. Triggering interrupt...")
                self.interrupt()
                if self.on_event:
                    self.on_event("clear_buffer", {"generation_id": self.current_generation_id})
            else:
                logger.debug(f"SPEECH_DETECTED[{self.session_id}]: Vol={rms:.0f}")
            
            self.speech_active = True
            self.silence_start_time = None
            self.last_speech_time = now
        else:
            if self.speech_active and self.silence_start_time is None:
                self.silence_start_time = now
                logger.debug(f"VAD_TRACE[{self.session_id}]: Speech STOP (Silence start)")
        
        # 3. Check Triggers
        should_process = False
        trigger_reason = ""
        current_buffer_seconds = len(self.audio_buffer) / (self.sample_rate * self.bytes_per_sample)
        
        # A: Smart Endpoint
        if self.speech_active and self.silence_start_time:
            silence_duration = now - self.silence_start_time
            if silence_duration > self.SILENCE_THRESHOLD:
                should_process = True
                trigger_reason = f"Smart Endpoint ({silence_duration:.2f}s silence)"
        
        # B: Constant Noise Valve
        if self.speech_active and not self.silence_start_time:
            if current_buffer_seconds > 8.0:
                 should_process = True
                 trigger_reason = f"Noise Valve ({current_buffer_seconds:.2f}s constant sound)"

        # C: Deaf Valve (Only if not already speaking/generating)
        if not self.speech_active and not self.is_speaking.is_set():
            if current_buffer_seconds > 3.0:
                should_process = True
                trigger_reason = f"Deaf Valve ({current_buffer_seconds:.2f}s no speech)"

        # D: Hard Limit
        if current_buffer_seconds > self.MAX_RECORDING_DURATION:
            should_process = True
            trigger_reason = "Hard Limit reached"
            
        # 4. Trigger Pipeline
        if should_process:
            logger.debug(f"STATE_TRACE[{self.session_id}]: {trigger_reason}")
            
            # Extract collected audio
            accumulated_audio = bytes(self.audio_buffer)
            
            # Reset State COMPLETELY
            self.audio_buffer.clear()
            self.speech_active = False
            self.silence_start_time = None
            
            # Execute pipeline (Non-blocking)
            if self.pipeline_task and not self.pipeline_task.done():
                self.pipeline_task.cancel()
                try:
                    # Vital: Wait for the task to actually finish/cleanup to prevent state races
                    await self.pipeline_task
                except asyncio.CancelledError:
                    pass
                
            self.current_generation_id += 1
            self.pipeline_task = asyncio.create_task(
                self._run_pipeline(accumulated_audio, self.current_generation_id)
            )

    def _heal_chat_history(self, session_id: str):
        """
        Detects all orphaned tool calls in history and injects error ToolMessages
        to satisfy LangGraph validation requirements.
        """
        config = {"configurable": {"thread_id": session_id}}
        state = self.agent.get_state(config)
        if not state or not state.values:
            return

        messages = state.values.get("messages", [])
        if not messages:
            return

        # Track all tool call IDs seen in AIMessages vs fulfilled by ToolMessages
        all_tool_call_ids = set()
        fulfilled_tool_call_ids = set()

        for msg in messages:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    all_tool_call_ids.add(tc.get('id'))
            elif isinstance(msg, ToolMessage):
                fulfilled_tool_call_ids.add(msg.tool_call_id)

        orphaned_ids = all_tool_call_ids - fulfilled_tool_call_ids
        
        if orphaned_ids:
            logger.warning(
                f"REPAIR: Found {len(orphaned_ids)} orphaned tool calls in session {session_id}. "
                f"Injecting healing ToolMessages for IDs: {orphaned_ids}"
            )
            healing_messages = []
            for tc_id in orphaned_ids:
                if tc_id:
                    healing_messages.append(ToolMessage(
                        tool_call_id=tc_id,
                        content="Error: Tool execution was interrupted by user or higher-level process.",
                        status="error"
                    ))
            
            if healing_messages:
                # Update the state with the healing messages. 
                # In LangGraph, update_state with as_node=None defaults to appending to 'messages'.
                self.agent.update_state(config, {"messages": healing_messages})

    async def _run_pipeline(self, audio_data: bytes, generation_id: int):
        """Execute the STT -> AI -> TTS pipeline and push to output_queue."""
        if not self.output_queue:
            return
            
        # Heal state before invocation to prevent INVALID_CHAT_HISTORY
        self._heal_chat_history(self.session_id)

        if self.on_event:
            self.on_event("status", {"state": "thinking"})

        with tracer.start_as_current_span("voice.agent.process") as span:
            span.set_attribute("session_id", self.session_id)
            span.set_attribute("voice.provider", self.stt_provider_name)
            span.set_attribute("audio_size_bytes", len(audio_data))
            
            # 1. Listen (STT)
            text_input = await self.stt.listen(audio_data, sample_rate=self.sample_rate)
            
            logger.debug(f"STT Transcript: '{text_input}'")
            
            if not text_input or len(text_input.strip()) < 2:
                logger.debug("Ignoring empty/short transcript.")
                return
                
            # Echo Suppression
            if self.last_agent_text:
                normalized_input = text_input.lower().strip()
                normalized_last = self.last_agent_text.lower().strip()
                if normalized_input in normalized_last or normalized_last in normalized_input:
                     if len(normalized_input) > 5 and (normalized_input == normalized_last or normalized_input in normalized_last):
                         logger.info(f"Ignoring potential echo: '{text_input}' matches last output.")
                         return

            logger.info(
                "User input received",
                extra={"session_id": self.session_id, "length": len(text_input), "text": text_input}
            )
            
            # 2. Pipeline: Agent -> Buffer -> TTS
            from backend.voice.buffer import SentenceBuffer
            buffer = SentenceBuffer()
            
            # Start generation logic
            self.is_speaking.set()
            
            try:
                text_stream = self._invoke_agent(text_input)
                sentence_stream = buffer.process(text_stream)
                
                # Update status to speaking as soon as we have a stream
                if self.on_event:
                    self.on_event("status", {"state": "speaking"})

                async for sentence in sentence_stream:
                    # CHECK INTERRUPT
                    if not self.is_speaking.is_set():
                        logger.info("Generation interrupted.")
                        break
                        
                    logger.debug(f"Synthesizing sentence: {sentence}")
                    
                    # Filter markdown for TTS
                    spoken_sentence = strip_markdown_for_tts(sentence)
                    if not spoken_sentence:
                        logger.debug("Skipping empty sentence after markdown strip.")
                        continue

                    # 3. Speak (TTS)
                    audio_output = await self.tts.speak(spoken_sentence)
                    
                    # FINAL CHECK: Did an interrupt happen during TTS synthesis?
                    if not self.is_speaking.is_set() or generation_id != self.current_generation_id:
                        logger.info(f"Discarding audio for obsolete generation {generation_id}")
                        break

                    # Push to shared output queue with generation_id prefixing
                    # We send a tuple (type, (gen_id, data))
                    await self.output_queue.put(("audio", (generation_id, audio_output)))
                    
                    await asyncio.sleep(0.01)
                    
            finally:
                self.is_speaking.clear()
                if self.on_event:
                    self.on_event("status", {"state": "listening"})

    def process_vad(self, audio_chunk: bytes) -> bool:
        """Check if audio chunk contains speech."""
        try:
            return self.vad.process(audio_chunk)
        except Exception:
            return False

    def interrupt(self):
        """Signal to stop speaking immediately."""
        if self.is_speaking.is_set():
            logger.warning("Interrupt signal received! Stopping generation.")
            self.is_speaking.clear()
            
            # Cancel active pipeline task if it exists
            if self.pipeline_task and not self.pipeline_task.done():
                self.pipeline_task.cancel()
                self.pipeline_task = None

            if self.vad:
                self.vad.reset()
            # Do NOT clear audio_buffer. We want to keep the speech that caused the interrupt.
            # We also don't reset speech_active because the user is currently middle-of-sentence.
            # We DO reset silence_start_time just in case.
            self.silence_start_time = None
    
    async def _invoke_agent(self, user_input: str) -> AsyncGenerator[str, None]:
        """Invoke LangGraph agent with streaming."""
        start = time.time()
        status = "success"
        
        if self.on_event:
            self.on_event("transcript", {"role": "user", "text": user_input})
        
        try:
            safe_input = self._sanitize_user_input(user_input)
            
            config = {
                "configurable": {"thread_id": self.session_id},
                "checkpointer": self.checkpointer
            }
            
            full_response = ""
            
            async for chunk in self.agent.astream(
                {"messages": [("user", safe_input)]},
                config=config,
                stream_mode="messages" 
            ):
                if isinstance(chunk, tuple):
                    chunk = chunk[0]
                
                if hasattr(chunk, 'content') and chunk.content:
                    AGENT_TOKENS.labels(model=self.model_name, type="completion").inc(1)
                    content = str(chunk.content)
                    full_response += content
                    
                    if self.on_event:
                         self.on_event("transcript", {"role": "assistant", "text": content, "partial": True})
                         
                    yield content
            
                # Send one final non-partial event to solidify the text (optional, but good for sync)
                self.on_event("transcript", {"role": "assistant", "text": full_response, "partial": False})
                self.last_agent_text = full_response
                
                # Persist history for offline review
                history = await get_chat_history(self.session_id)
                _persist_session_history(self.session_id, history)

            AGENT_REQUESTS.labels(model=self.model_name, status=status).inc()
            
        except Exception as e:
            status = "error"
            AGENT_REQUESTS.labels(model=self.model_name, status=status).inc()
            logger.error(f"Agent invocation failed: {e}")
            yield "I'm sorry, I encountered an error."
        finally:
            AGENT_LATENCY.labels(model=self.model_name).observe(time.time() - start)

    def _sanitize_user_input(self, text: str) -> str:
        """Sanitize user input."""
        forbidden_phrases = ["ignore previous", "ignore all previous", "system:", "assistant:", "set context", "you are now"]
        sanitized = text
        for phrase in forbidden_phrases:
            # Case-insensitive replacement
            sanitized = re.sub(re.escape(phrase), "[redacted]", sanitized, flags=re.IGNORECASE)
        return sanitized[:1000]

    async def handle_text_input(self, text: str):
        """
        Processes manual text input from the UI.
        Interrupts any current generation and triggers the pipeline.
        """
        logger.info(f"Processing manual text input: {text[:50]}...")
        
        # 1. Interrupt any current generation
        self.interrupt()
        # Wait for pipeline to potentially clean up if it was running (though interrupt() just signals)
        # interrupt() cancels the task, but doesn't await it. We should await if we can.
        if self.pipeline_task and not self.pipeline_task.done():
             try:
                 await self.pipeline_task
             except asyncio.CancelledError:
                 pass
        
        # 2. Reset state
        self.audio_buffer.clear()
        self.speech_active = False
        self.silence_start_time = None
        
        # 3. Trigger pipeline with new generation ID
        self.current_generation_id += 1
        
        # 4. We bypass STT and call the generation logic directly
        # But we create a wrapper or just use _run_pipeline's inner part?
        # Actually _run_pipeline does STT. Let's create a specialized task or refactor.
        
        # Refactor: _run_pipeline should take text optionally
        self.pipeline_task = asyncio.create_task(
            self._run_pipeline_text(text, self.current_generation_id)
        )

    async def _run_pipeline_text(self, text_input: str, generation_id: int):
        """Execute the Agent -> TTS part of the pipeline directly."""
        if not self.output_queue:
            return
            
        # Heal state before invocation
        self._heal_chat_history(self.session_id)

        if self.on_event:
            self.on_event("status", {"state": "thinking"})

        with tracer.start_as_current_span("voice.agent.process_text") as span:
            span.set_attribute("session_id", self.session_id)
            span.set_attribute("input_length", len(text_input))
            
            logger.info(
                "Manual text input processing",
                extra={"session_id": self.session_id, "length": len(text_input), "text": text_input}
            )
            
            # 2. Pipeline: Agent -> Buffer -> TTS
            from backend.voice.buffer import SentenceBuffer
            buffer = SentenceBuffer()
            
            self.is_speaking.set()
            
            try:
                text_stream = self._invoke_agent(text_input)
                sentence_stream = buffer.process(text_stream)
                
                if self.on_event:
                    self.on_event("status", {"state": "speaking"})

                async for sentence in sentence_stream:
                    if not self.is_speaking.is_set():
                        break
                        
                    spoken_sentence = strip_markdown_for_tts(sentence)
                    if not spoken_sentence:
                        continue

                    audio_output = await self.tts.speak(spoken_sentence)
                    
                    if not self.is_speaking.is_set() or generation_id != self.current_generation_id:
                        break

                    await self.output_queue.put(("audio", (generation_id, audio_output)))
                    await asyncio.sleep(0.01)
                    
            finally:
                self.is_speaking.clear()
                if self.on_event:
                    self.on_event("status", {"state": "listening"})

