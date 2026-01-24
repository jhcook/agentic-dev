# INFRA-035-runbook.md

## Status

ACCEPTED

## Goal

Implement "Barge-in" capability for the Voice Agent. This requires Voice Activity Detection (VAD) to recognize when the user starts speaking while the agent is talking, and an Interrupt Handler to immediately stop audio playback and update the conversation context.

## Panel Review Findings

### @Architect

**Sentiment**: Neutral (Concurrency Complexity)
**Advice**:

- **State Management**: The "Speaking" state must be carefully managed. If VAD triggers an interrupt, we must:
  1. Cancel the current TTS generation task.
  2. Tell the client to drop valid audio chunks it has buffered.
  3. Tell the Agent it was interrupted (optional for MVP, good for polish).
- **Library Choice**: `silero-vad` is recommended for high accuracy and ease of use (Onnx).

### @Backend

**Sentiment**: Positive
**Advice**:

- **Asyncio Events**: Use `asyncio.Event` to signal stop requests to the generator pipeline.
- **Dependencies**: Add `silero-vad`, `onnxruntime` (already present for Kokoro?). If `onnxruntime` is issue on 3.14, consider `webrtcvad` (requires C compilation) or `speechrecognition`. *Note: Kokoro uses `kokoro-onnx`, ensuring ONNX is viable if installed correctly.*

### @QA

**Sentiment**: Positive
**Advice**:

- **False Positives**: Tunable threshold for VAD is essential.
- **Testing**: Test "Double Talk" – user speaks, stops, agent speaks, user interrupts.

### @Product

**Sentiment**: Positive
**Advice**:

- **Latency**: User must feel the agent stop *instantly*.

## Implementation Steps

### 1. Add VAD Dependency

**File**: `.agent/pyproject.toml`

- Add `silero-vad` or simpler `webrtcvad`.
- *Choice*: `silero` via `torch` hub or `onnx`. Given `kokoro-onnx` presence, let's use a lightweight VAD solution compatible with our stack.
- *Decision*: Try `silero-vad` via `onnxruntime` since we already depend on `onnxruntime` for Kokoro.

### 2. Implement VAD Processor

**File**: `.agent/src/backend/voice/vad.py`
Create `VADProcessor` class.

- **Input**: Audio chunks (bytes).
- **Output**: Boolean `is_speech`.
- **Logic**: Buffer chunks to required window (e.g. 30ms), run VAD model.

### 3. Update VoiceOrchestrator

**File**: `.agent/src/backend/voice/orchestrator.py`

- Add `self.is_speaking` flag (managed via `asyncio.Event`).
- **Concurrency**: Split input stream:
  - Stream A -> STT Provider (transcription).
  - Stream B -> VAD Processor (interrupt detection).
- **Interrupt Logic**:
  - Check `vad_threshold` (from config).
  - Enforce `interrupt_cooldown` (e.g., 1.5s) to prevent "stuttering".
  - If triggered:
    - Set `interrupt_signal`.
    - Break `process_audio` generator loop.
    - Yield `ControlMessage` (Stop/Clear) to Router.

### 4. Update WebSocket Router

**File**: `.agent/src/backend/routers/voice.py`

- Handle control messages from Orchestrator.
- **Protocol**: Send `{"type": "clear_buffer"}` JSON frame to client.
- Client must clear audio queue immediately upon receipt.

## Verification Plan

### Automated Tests

1. **Unit**: `tests/test_vad.py`
   - Feed silence -> False.
   - Feed noise > threshold -> True.
2. **Integration**: `tests/test_interrupt.py`
   - Mock VAD to trigger "True" mid-generation. verify generator exits.

### Manual Verification

1. Connect via Client.
2. Ask a long question.
3. Interrupt "Stop!"
4. Agent should silence immediately.
