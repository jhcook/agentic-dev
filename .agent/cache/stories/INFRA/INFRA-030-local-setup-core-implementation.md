# INFRA-030: Local Setup & Core Implementation

## State

COMMITTED

## Linked Plan

INFRA-030

## Problem Statement

We need to set up the local environment and implement the core service layer for offline voice processing using Kokoro (TTS) and Faster-Whisper (STT).

## User Story

As a developer/user, I want a local voice service that runs offline, so that I can use voice features without internet or cloud costs.

## Acceptance Criteria

- [ ] **Filesystem Setup**: Models (`kokoro-v0_19.onnx`, `voices.json`, `af_sarah`) are downloaded to `backend/models/kokoro/`.
- [ ] **Dependencies**: `kokoro-onnx` and `soundfile` are installed.
- [ ] **Service Layer**: `backend/services/voice/local.py` is created.
- [ ] **Implementation**: `LocalTTS` class initializes the ONNX model and implements the `TTSProvider` interface.
- [ ] **Audio Formatting**: Resample Kokoro output (24kHz) if necessary to match client expectations (e.g. 16kHz).
- [ ] **Model Config**: Model paths are configurable via env vars or config, not hardcoded.
- [ ] **Synthesis**: `create()` method generates audio from text within acceptable time (~200ms/sentence).

## Non-Functional Requirements

- **Hardware**: Must run on M1/M2 Mac or NVIDIA GPU (4GB+).
- **Memory**: Model loading should consume ~300MB RAM.
- **Audio Quality**: Output sample rate must be consistent (explicitly handled).

## Linked ADRs

- ADR-009

## Impact Analysis Summary

Components touched: `backend/services/voice/local.py`
Workflows affected: Offline Voice
Risks identified:

- Hardware compatibility issues.
- **Sample Rate Mismatch**: Kokoro (24kHz) vs Deepgram/Standard (16kHz).

## Test Strategy

- **CI Safety**: Unit tests MUST mock `Kokoro` and NOT download model files.
- Unit test ensuring model loads and `create()` returns audio bytes.

## Rollback Plan

- Delete models and code.
