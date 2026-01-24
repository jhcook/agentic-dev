# INFRA-031-runbook.md

## Status

ACCEPTED

## Goal

Refactor the voice processing pipeline to support real-time streaming with natural prosody. This involves moving from a request/response model to an asynchronous generator pipeline (`Agent -> SentenceBuffer -> TTS -> Audio Stream`) to drive the local `Kokoro` TTS (and cloud providers) efficiently.

## Panel Review Findings

### @Architect

**Sentiment**: Neutral (Refactor Required)
**Advice**:

- **Streaming Pipeline**: The `VoiceOrchestrator.process_audio` MUST return an `AsyncGenerator[bytes]` to enable true streaming.
- **Component**: Isolate sentence buffering logic into `backend.voice.buffer.SentenceBuffer`.
- **Concurrency**: Ensure the pipeline allows the Agent to generate text while TTS synthesizes audio concurrently.

### @Backend

**Sentiment**: Warning (Bug)
**Advice**:

- **Fix Streaming**: Current `_invoke_agent` likely exits on the first token. Fix it to yield all chunks.
- **Generator Pattern**: Use Python `async yield` extensively to propagate data through the pipeline.

### @QA

**Sentiment**: Positive
**Advice**:

- **Unit Tests**: Verification of `SentenceBuffer` is critical. Test with:
  - "Hello world." (Standard)
  - "Mr. Smith is here." (Abbreviation vs End of Sentence)
  - "One... two... three!" (Ellipsis)
- **Latency**: Measure Time-to-First-Byte (TTFB).

### @Product

**Sentiment**: Positive
**Advice**:

- **Quality First**: Buffering full sentences is acceptable even if it adds slight latency (~200ms) because it prevents "robotic" intonation.

## Implementation Steps

### 1. Implement SentenceBuffer

**File**: `.agent/src/backend/voice/buffer.py`
Create a class that accumulates text tokens and yields complete sentences.

- **Logic**: Append tokens. Check for punctuation (`.`, `?`, `!`, `\n`).
- **Edge Cases**: Handle abbreviations (optional for MVP, but good to check). Flush remainder on stream end.

### 2. Refactor VoiceOrchestrator

**File**: `.agent/src/backend/voice/orchestrator.py`

**A. Fix `_invoke_agent`**:
Turn it into an `AsyncGenerator[str]` that yields text chunks (tokens or phrases) from LangGraph.

**B. Update `process_audio`**:
Change return type to `AsyncGenerator[bytes, None]`.
Pipeline:

```python
async def process_audio(self, audio_chunk: bytes):
    # ... STT ...
    text_input = await self.stt.listen(audio_chunk)
    
    # Create Pipeline
    text_stream = self._invoke_agent(text_input)
    sentence_stream = self.buffer.process(text_stream)
    
    async for sentence in sentence_stream:
        # TTS works per sentence
        audio = await self.tts.speak(sentence)
        yield audio
```

### 3. Update WebSocket Router

**File**: `.agent/src/backend/routers/voice.py`
Update the loop to consume the generator:

```python
async for chunk in orchestrator.process_audio(data):
    await websocket.send_bytes(chunk)
```

## Verification Plan

### Automated Tests

1. **Unit**: `tests/test_sentence_buffer.py`
   - Test accumulation and splitting.
2. **Integration**: `tests/test_voice_flow.py`
   - Update to handle async generator response from `orchestrator.process_audio`.

### Manual Verification

1. Connect via Client.
2. Speak a complex query.
3. Listen: Audio should start playing *before* the agent finishes "thinking" (if sentence is short), or at least flow smoothly sentence-by-sentence.
