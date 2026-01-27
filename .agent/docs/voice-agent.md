# Voice Agent Features & Configuration

## Hybrid VAD Strategy (ADR-012)

The Voice Agent uses a sophisticated hybrid Voice Activity Detection (VAD) system to ensure responsiveness and accuracy across different environments.

### 1. Silero VAD (Primary)

- **Engine**: ONNX Runtime
- **Quality**: High accuracy, robust against background noise.
- **Behavior**: Used by default if the model can be downloaded and verified.

### 2. WebRTC VAD (Fallback)

- **Engine**: Google WebRTC
- **Quality**: Good standard VAD, very low latency.
- **Behavior**: Automatic backup if Silero fails to initialize.

### 3. Adaptive Energy Gate (Global)

- **Engine**: RMS / Signal-to-Noise Ratio
- **Purpose**: Prevents the high-accuracy models from processing pure silence, saving CPU.
- **Autotuning**:
  - Continuously measures ambient noise floor.
  - Dynamically adjusts threshold (default `2.2x` noise floor).
  - Adapts to changing environments (e.g. AC turning on).

## Configuration (`.agent/etc/voice.yaml`)

```yaml
vad:
  aggressiveness: 3          # WebRTC aggressiveness (0-3)
  silence_threshold: 0.8     # Silero silence confidence
  threshold: 0.5             # Silero speech probability threshold
  autotune: true             # Enable adaptive energy gating (Recommended: true)
```

### Tuning Guide

- **Too sensitive?** Increase `threshold` (e.g. `0.6`) or disable `autotune` if environment is extremely noisy.
- **Not picking up voice?** Lower `threshold` (e.g. `0.4`) or check microphone gain.
