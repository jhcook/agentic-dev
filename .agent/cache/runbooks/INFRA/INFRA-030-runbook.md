# INFRA-030-runbook.md

## Status

ACCEPTED

## Goal

Set up the local environment and implement the core service layer for offline voice processing using Kokoro (TTS) and Faster-Whisper (STT), enabling "zero-cost" and "air-gapped" voice capabilities.

## Panel Review Findings

### @Architect

**Sentiment**: Positive
**Advice**:

- **Abstraction**: `LocalTTS` must strictly implement `TTSProvider` protocol.
- **Config**: Use `agent.core.config` to locate model files, defaulting to user data dir or `.agent/cache/models`. NEVER hardcode paths.
- **Resampling**: Kokoro outputs 24kHz. Use `scipy` or `librosa` (or pure python if possible to avoid deps) to resample to 16kHz to match system standard. `scipy` is robust.

### @Security

**Sentiment**: Positive
**Advice**:

- **Model Integrity**: Verify SHA256 checksum of downloaded ONNX models to prevent supply chain attacks.
- **Input Cleaning**: Ensure text sent to `kokoro-onnx` doesn't trigger unexpected behavior (standard sanitization).

### @QA

**Sentiment**: Neutral (Caveats)
**Advice**:

- **CI Safety**: Unit tests must mock `Kokoro` class. Do NOT download models in CI.
- **Integration Test**: Skipped if model file missing.
- **Performance**: Benchmark generation speed.

### @Mobile / @Backend

**Sentiment**: Warning
**Advice**:

- **Audio Format**: Crucial to resample 24kHz -> 16kHz to avoid pitch shifting on playback.
- **Dependencies**: `soundfile` needs `libsndfile`.

## Implementation Steps

### 1. Add Dependencies

**File**: `.agent/pyproject.toml`
Add:

- `kokoro-onnx`
- `soundfile`
- `scipy` (for resampling) or `numpy`
- `requests` (for downloading models)

```bash
poetry add kokoro-onnx soundfile scipy
```

### 2. Create Model Downloader Utility

**File**: `.agent/src/backend/scripts/download_models.py`
Create a script to download `kokoro-v0_19.onnx` and `voices.json` to a configurable location.

- Default path: `.agent/models/kokoro/`
- Verify checksums.

### 3. Implement LocalTTS Service

**File**: `.agent/src/backend/speech/providers/local.py`
Implement `LocalTTS` class implementing `TTSProvider`.

**Key Logic**:

- Initialize `Kokoro` with model path.
- `speak(text)`:
  - Generate audio (returns samples, 24000hz).
  - Resample to 16000hz using `scipy.signal.resample` (or similar efficient method).
  - Convert to bytes (WAV or raw PCM).

### 4. Update Factory

**File**: `.agent/src/backend/speech/factory.py`
Update `get_voice_providers` to return `LocalTTS` if `VOICE_PROVIDER=local`.

## Verification Plan

### Automated Tests

1. **Unit**: `test_local_tts.py`
   - Mock `Kokoro` and `scipy`.
   - Verify `speak` calls generate -> resample -> return bytes.
2. **Integration** (Local only):
   - Run only if models exist.
   - Generate "Hello World.wav".
   - Check file header for 16kHz sample rate.

### Manual Verification

1. Run downloader script.
2. Configure `VOICE_PROVIDER=local`.
3. Start backend.
4. Speak to websocket -> Verify response voice is Kokoro (not Deepgram).
