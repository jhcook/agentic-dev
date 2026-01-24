# WEB-001: Voice Web Client

## State

COMMITTED

## Problem Statement

The Voice capabilities (INFRA-030/031/035) are currently accessible only via raw WebSocket scripts or CLI tools. Users need a user-friendly, visual interface to interact with the voice agent comfortably.

## User Story

As a User, I want a rich web interface to speak with the agent, see its status (Listening/Thinking/Speaking), and view a transcript of our conversation, so that the experience feels like a modern voice assistant.

## Acceptance Criteria

- [ ] **Project Setup**: Initialize `web/` with React, Vite, and TailwindCSS.
- [ ] **Audio Capture**: Implement `AudioWorklet` to capture microphone input and downsample to 16kHz PCM (backend requirement).
- [ ] **Streaming**: Connect to `ws://localhost:8000/ws/voice` and stream audio bidirectionally.
- [ ] **Visualization**: Render real-time audio waveforms (e.g. using Canvas API) for both input and output audio.
- [ ] **Protocol Support**: Handle the `clear_buffer` control message to stop playback instantly on interrupt.

## Non-Functional Requirements

- **Latency**: Audio processing overhead < 20ms.
- **Aesthetics**: "Dark Mode" by default, smooth animations.

## Linked ADRs

- ADR-009 (Voice Stack)

## Impact Analysis Summary

Components touched: New `web/` directory.
Workflows affected: Development workflow (needs `npm` in addition to `python`).
Risks: Browser AudioContext compatibility.

## Test Strategy

- Browser automation (optional/future).
- Manual "Barge-in" testing.

## Rollback Plan

- Delete `web/` directory.
