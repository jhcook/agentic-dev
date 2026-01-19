# ADR-009: Offline Local Voice Stack

## Status
ACCEPTED

## Context
For development, testing, and privacy-conscious users, relying solely on a cloud provider (Deepgram) is insufficient. We need a "zero-cost" and "air-gapped" alternative.

## Decision
We will implement an offline-capable voice stack using open-source models:
- **STT:** `faster-whisper` (optimized Whisper implementation).
- **TTS:** `kokoro-onnx` (lightweight, high-quality, <100MB model).

This stack must run on consumer hardware (M1/M2 Mac, NVIDIA GPU) with reasonable latency.

## Consequences
### Positive
- **Privacy:** No audio data leaves the device.
- **Cost:** Free (excluding hardware).
- **Offline:** Works without internet.

### Negative
- **Resource Usage:** Consumes RAM (~300MB+) and CPU/GPU.
- **Latency:** Higher than cloud equivalents on lower-end hardware.
- **Installation:** Users must download model weights (GBs).
