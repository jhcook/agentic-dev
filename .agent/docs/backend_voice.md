# Backend Voice Integration

Complete guide to the voice provider architecture, Deepgram integration, and real-time voice orchestration via WebSocket.

## Overview

The backend voice integration provides a flexible, provider-agnostic abstraction for Speech-to-Text (STT) and Text-to-Speech (TTS) services, with comprehensive observability and real-time orchestration capabilities.

**Key Components**:

- **Provider Interfaces** - Abstract STT/TTS protocols
- **Deepgram Integration** - Production-ready implementation using Deepgram SDK v5.3.1
- **Voice Orchestrator** - Manages STT → Agent → TTS flow
- **WebSocket Endpoint** - Real-time bidirectional audio streaming
- **Observability** - Prometheus metrics, OpenTelemetry tracing, structured logging

---

## Architecture

### Directory Structure

```
.agent/src/backend/
├── speech/
│   ├── __init__.py
│   ├── interfaces.py          # STTProvider & TTSProvider protocols
│   ├── factory.py             # Provider instantiation
│   └── providers/
│       ├── __init__.py
│       └── deepgram.py        # Deepgram implementation
├── voice/
│   ├── __init__.py
│   └── orchestrator.py        # VoiceOrchestrator class
├── routers/
│   ├── __init__.py
│   └── voice.py               # /ws/voice WebSocket endpoint
└── main.py                    # FastAPI application entry point
```

### Component Flow

```mermaid
graph TB
    Client[WebSocket Client] -->|Audio Chunks| Router[/ws/voice Router]
    Router --> Orchestrator[VoiceOrchestrator]
    Orchestrator --> Factory[get_voice_providers]
    Factory --> STT[DeepgramSTT]
    Factory --> TTS[DeepgramTTS]
    Orchestrator -->|Audio Data| STT
    STT -->|Transcript| Agent[Placeholder Agent]
    Agent -->|Response Text| TTS
    TTS -->|Audio Bytes| Orchestrator
    Orchestrator -->|Audio Response| Router
    Router -->|Stream| Client
```

---

## Provider Interfaces

### STTProvider Protocol

**File**: [interfaces.py](file:///Users/jcook/repo/agentic-dev/.agent/src/backend/speech/interfaces.py)

```python
from typing import Protocol

class STTProvider(Protocol):
    """Speech-to-Text provider interface."""
    
    async def listen(self, audio_data: bytes) -> str:
        """Convert audio bytes to text transcript."""
        ...
    
    async def health_check(self) -> bool:
        """Check if the provider is healthy and reachable."""
        ...
```

### TTSProvider Protocol

```python
class TTSProvider(Protocol):
    """Text-to-Speech provider interface."""
    
    async def speak(self, text: str) -> bytes:
        """Convert text to audio bytes."""
        ...
    
    async def health_check(self) -> bool:
        """Check if the provider is healthy and reachable."""
        ...
```

**Benefits of Protocol-Based Design**:

- ✅ Easy to add new providers (e.g., Google Cloud, Azure)
- ✅ Supports dependency injection for testing
- ✅ Type-safe with static analysis tools (mypy, pyright)

---

## Deepgram Integration

### Configuration

**API Key Setup**:

```bash
# Using the Agent secret manager (recommended)
.venv/bin/python -m agent secret set deepgram api_key YOUR_DEEPGRAM_API_KEY

# Or via environment variable
export DEEPGRAM_API_KEY=YOUR_DEEPGRAM_API_KEY
```

The factory uses the secure secret manager (`agent.core.secrets.get_secret`) which integrates with the system keychain.

### Deepgram SDK v5.3.1 Specifics

**Important**: The Deepgram SDK v5 has significant API changes from v3/v4:

#### STT (Speech-to-Text)

- **Method**: `client.listen.v1.media.transcribe_file()`
- **Signature**: Keyword-only arguments (starts with `*,`)
- **Synchronous**: Returns response directly, not awaitable
- **Solution**: Wrapped in `asyncio.to_thread()` to prevent event loop blocking

**Example**:

```python
response = await asyncio.to_thread(
    self.client.listen.v1.media.transcribe_file,
    request=audio_data,
    model="nova-2",
    smart_format=True
)
transcript = response.results.channels[0].alternatives[0].transcript
```

#### TTS (Text-to-Speech)

- **Method**: `client.speak.v1.audio.generate()`
- **Signature**: Keyword-only arguments (starts with `*,`)
- **Returns**: `Iterator[bytes]` (synchronous generator)
- **Solution**: Consume generator in thread pool

**Example**:

```python
def _consume_generator():
    chunks = self.client.speak.v1.audio.generate(
        text=text,
        model="aura-asteria-en"
    )
    return b"".join(chunks)

audio_bytes = await asyncio.to_thread(_consume_generator)
```

```python
# Must use keyword argument
from deepgram import DeepgramClient
client = DeepgramClient(api_key=api_key)
```

---

## LLM Configuration

The conversational agent can be configured to use different LLM providers (OpenAI, Anthropic, Gemini).

### Provider Selection

Use the `agent config` command to update `.agent/etc/voice.yaml`:

```bash
# Switch to Gemini
agent config set llm.provider gemini --file voice.yaml
agent config set llm.model gemini-2.0-flash-exp --file voice.yaml

# Switch to OpenAI
agent config set llm.provider openai --file voice.yaml
agent config set llm.model gpt-4o-mini --file voice.yaml
```

### API Keys

Ensure the API key for the selected provider is set in the secure secret manager:

```bash
# Gemini
.venv/bin/python -m agent secret set gemini api_key YOUR_GEMINI_KEY

# OpenAI
.venv/bin/python -m agent secret set openai api_key YOUR_OPENAI_KEY

# Anthropic
.venv/bin/python -m agent secret set anthropic api_key YOUR_ANTHROPIC_KEY
```

---

## Observability

### Metrics (Prometheus)

**Exposed Metrics**:

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `voice_provider_requests_total` | Counter | `provider`, `type` | Total requests to STT/TTS |
| `voice_provider_request_duration_seconds` | Histogram | `provider`, `type` | Request latency |
| `voice_provider_errors_total` | Counter | `provider`, `type`, `error_type` | Error count by type |

**Example Query** (Prometheus):

```promql
# Average TTS latency over 5 minutes
rate(voice_provider_request_duration_seconds_sum{type="tts"}[5m]) 
  / rate(voice_provider_request_duration_seconds_count{type="tts"}[5m])
```

### Tracing (OpenTelemetry)

Each STT/TTS operation creates a span:

- `deepgram.stt.listen` - STT transcription
- `deepgram.tts.speak` - TTS synthesis

**Correlation IDs**:

- Extracted from OpenTelemetry trace context
- Added as `correlation_id` span attribute
- Included in all log messages for request tracing

### Structured Logging

**Log Format**:

```json
{
  "level": "INFO",
  "message": "Sending TTS request to Deepgram.",
  "provider": "deepgram",
  "correlation_id": "f89b7c1f367f9268162b790a3e2de9ef0423d355"
}
```

**PII Safety**:

- ❌ No audio data in logs
- ❌ No transcripts in standard logs
- ✅ Metadata only (provider, duration, error types)

---

## Voice Orchestration

### VoiceOrchestrator Class

**File**: [orchestrator.py](file:///Users/jcook/repo/agentic-dev/.agent/src/backend/voice/orchestrator.py)

**Responsibilities**:

1. Manage conversation history per session
2. Orchestrate STT → Agent → TTS flow
3. Handle async audio processing
4. Provide error handling and logging

**Usage**:

```python
from backend.voice.orchestrator import VoiceOrchestrator

orchestrator = VoiceOrchestrator(session_id="user-123")
audio_response = await orchestrator.process_audio(audio_chunk)
```

**Agent Integration** (Placeholder):
Currently uses a simple echo agent. To integrate a real agent (e.g., LangGraph):

```python
# In orchestrator.py
async def _invoke_agent(self, transcript: str) -> str:
    # TODO: Replace with LangGraph integration
    # from your_agent import YourAgent
    # response = await YourAgent.achat(self.history, transcript)
    return f"Agent: {transcript}"
```

### WebSocket Endpoint

**File**: [voice.py](file:///Users/jcook/repo/agentic-dev/.agent/src/backend/routers/voice.py)

**Endpoint**: `ws://localhost:8000/ws/voice`

**Protocol**:

1. Client connects to WebSocket
2. Client sends binary audio chunks
3. Server processes via `VoiceOrchestrator`
4. Server streams audio response back
5. Connection persists for multi-turn conversation

**Example Client** (JavaScript):

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/voice');

ws.onopen = () => {
  // Send audio chunk (e.g., from microphone)
  ws.send(audioChunk);
};

ws.onmessage = (event) => {
  // Receive audio response
  const audioResponse = event.data;
  playAudio(audioResponse);
};
```

---

## Testing

### Integration Tests

**File**: [test_voice_flow.py](file:///Users/jcook/repo/agentic-dev/.agent/tests/test_voice_flow.py)

**Running Tests**:

```bash
cd .agent
.venv/bin/python -m pytest tests/test_voice_flow.py -v
```

**What's Tested**:

- ✅ WebSocket connection establishment
- ✅ Audio packet flow (mocked providers)
- ✅ Echo functionality (placeholder agent)
- ✅ Response validation

**Mocking Strategy**:

```python
from unittest.mock import AsyncMock

# Mock providers to isolate WebSocket logic
mock_stt = AsyncMock(return_value="hello")
mock_tts = AsyncMock(return_value=b"fake-audio-data")
```

### Manual Testing

**Start the Server**:

```bash
cd .agent/src
uvicorn backend.main:app --reload
```

**Test with wscat**:

```bash
npm install -g wscat
wscat -c ws://localhost:8000/ws/voice -b
# Send binary data interactively
```

**Health Check**:

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok"}
```

---

## Known Issues & Troubleshooting

### SSL Certificate Validation Error

**Symptom**:

```
[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: Missing Authority Key Identifier
```

**Root Cause**:
This occurs when connecting to `api.deepgram.com` through a corporate proxy that intercepts SSL certificates. The intercepted certificate may lack proper Authority Key Identifier extensions.

**Solution**:

1. **Trust the proxy certificate** on your system
2. **Configure proxy bypass** for `api.deepgram.com`
3. **Disable certificate interception** for Deepgram endpoints

**Verification**:

```bash
# Test direct connection (should succeed)
curl -v https://api.deepgram.com

# Check certificate chain
openssl s_client -connect api.deepgram.com:443 -servername api.deepgram.com
```

**Note**: This does NOT affect:

- ✅ Integration tests (use mocks, no API calls)
- ✅ Production deployments (typically no intercepting proxies)
- ✅ The Deepgram API itself (certificate is valid)

### Pydantic v1 Warning

**Warning**:

```
UserWarning: Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.
```

**Impact**: Cosmetic only. Deepgram SDK uses Pydantic v1 internally, which shows a deprecation warning on Python 3.14.

**Resolution**: No action needed. Wait for Deepgram SDK to update to Pydantic v2.

---

## Dependencies

### Required Packages

```toml
[project.dependencies]
fastapi = ">=0.100.0"
uvicorn = ">=0.23.0"
deepgram-sdk = ">=3.0"
prometheus-client = ">=0.17.0"
opentelemetry-api = ">=1.20.0"
opentelemetry-sdk = ">=1.20.0"
keyring = ">=24.0.0"
cryptography = ">=41.0.0"
```

### Installation

```bash
cd .agent
poetry install
# or
.venv/bin/pip install -e .
```

---

## Production Deployment

### Environment Variables

```bash
# Option 1: Use secret manager (recommended)
.venv/bin/python -m agent secret set deepgram api_key YOUR_KEY

# Option 2: Environment variable
export DEEPGRAM_API_KEY=YOUR_KEY
```

### Running the Server

**Development**:

```bash
cd .agent/src
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Production** (with Gunicorn):

```bash
gunicorn backend.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

### Security Considerations

1. **Authentication**: Add WebSocket authentication

   ```python
   # In voice.py
   @router.websocket("/ws/voice")
   async def websocket_voice(websocket: WebSocket, token: str = Query(...)):
       # Validate token before accept()
       if not validate_token(token):
           await websocket.close(code=4001)
           return
       await websocket.accept()
   ```

2. **Rate Limiting**: Implement connection limits per user
3. **Input Validation**: Validate audio chunk sizes/formats
4. **CORS**: Configure allowed origins for WebSocket connections

### Monitoring

**Prometheus Scraping**:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'voice-backend'
    static_configs:
      - targets: ['localhost:8000']
```

**Grafana Dashboard** (suggested metrics):

- Voice session duration (p50, p95, p99)
- TTS/STT latency
- Error rates by provider
- Active WebSocket connections

---

## Next Steps

### 1. Integrate Real Agent (INFRA-034)

Replace the placeholder agent in `orchestrator.py`:

```python
# Example: LangGraph integration
from langgraph import create_agent

class VoiceOrchestrator:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.agent = create_agent(...)  # Your agent setup
        
    async def _invoke_agent(self, transcript: str) -> str:
        response = await self.agent.arun(transcript)
        return response
```

### 2. Add More Providers

Implement Google Cloud Speech or Azure Cognitive Services:

```python
# backend/speech/providers/google_cloud.py
class GoogleCloudSTT:
    async def listen(self, audio_data: bytes) -> str:
        # Implement Google Cloud Speech API
        ...
```

### 3. Enhanced Orchestration

- Add conversation state persistence
- Implement turn-taking logic
- Support streaming STT (live transcription)
- Add interrupt handling (user interrupts agent)

### 4. Advanced Features

- Multi-language support
- Voice activity detection (VAD)
- Custom voice models
- Real-time translation

---

## References

- **Deepgram API Docs**: <https://developers.deepgram.com/>
- **Deepgram SDK v5**: <https://github.com/deepgram/deepgram-python-sdk>
- **FastAPI WebSockets**: <https://fastapi.tiangolo.com/advanced/websockets/>
- **OpenTelemetry Python**: <https://opentelemetry.io/docs/languages/python/>
- **Prometheus Client**: <https://github.com/prometheus/client_python>

---

## Support

For issues or questions:

1. Check [Troubleshooting](#known-issues--troubleshooting)
2. Review integration tests for usage examples
3. Consult Deepgram SDK documentation for API changes
4. Check story files: `INFRA-027` (observability), `INFRA-028` (orchestration)
