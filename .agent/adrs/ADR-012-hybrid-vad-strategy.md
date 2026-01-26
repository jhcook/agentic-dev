# ADR-012: Hybrid Voice Activity Detection Strategy

## Status

COMMITTED

## Context

The voice agent requires highly accurate and noise-resistant Voice Activity Detection (VAD) to enable reliable "barge-in" (the ability for the user to interrupt the agent).

- **Silero VAD** is the industry standard for lightweight, high-quality, local-first VAD.
- **Google WebRTC VAD** is a standard, extremely lightweight C-based VAD.
- **Issue**: Silero requires `onnxruntime`, which currently has binary compatibility issues on Python 3.14 in certain environments (e.g., Apple Silicon with specific Cython versions).

## Decision

We will implement a **Hybrid VAD Strategy**:

1. **Prefer Silero**: The system will attempt to initialize Silero VAD (ONNX) as the primary engine.
2. **Fallback to WebRTC**: If Silero initialization fails (missing dependency, model not found, or environment error), the system will automatically fall back to Google WebRTC VAD.
3. **Unified Interface**: Both implementations will be encapsulated behind the `VADProcessor` class in `vad.py`.

## Consequences

### Positive

- **Best Effort Quality**: Most users get high-quality VAD.
- **Environment Robustness**: The agent remains functional even on Python 3.14 where Silero might be broken.
- **Architectural Cleanliness**: One class handles all VAD logic, simplifying the orchestrator.

### Negative

- **Inconsistency**: Different users might experience different VAD quality depending on their environment.
- **Maintenance**: We must maintain two separate VAD implementation paths in the code.

## Compliance & Security

### Data Retention

- The Silero VAD model file (`.agent/storage/silero_vad.onnx`) is a static asset downloaded from GitHub.
- **Content**: It contains model weights only; no user data.
- **Retention**: Persists until the user manually clears the `.agent/storage/` directory or uninstalls the agent.
- **Deletion**: The agent attempts to delete the file automatically if integrity verification fails.

### Licensing

- **Silero VAD**: MIT License (Permissive).
- **WebRTC VAD**: MIT License (Permissive).

### Integrity

- The model file is verified against a hardcoded SHA256 checksum before every use.
- File permissions are restricted to `0o600` (User Read/Write only) to prevent unauthorized local modification.
