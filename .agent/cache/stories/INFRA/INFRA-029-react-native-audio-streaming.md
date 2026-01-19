# INFRA-029: React Native Audio Streaming

## State
COMMITTED

## Linked Plan
INFRA-027

## Problem Statement
The mobile app needs to capture microphone input and play back streaming audio (chunks) received via WebSocket, which is different from playing a static MP3 file.

## User Story
As a Mobile User, I want the app to capture my voice and play back the assistant's voice smoothly without waiting for the full sentence to download.

## Acceptance Criteria
- [ ] **Microphone Input**: App captures audio (PCM 16-bit, 16kHz preferred) and streams it to WebSocket.
- [ ] **Stream Playback**: App accepts audio chunks and plays them immediately (handling partial chunks/buffering).
- [ ] **Audio Focus**: App handles interruptions (phone calls, other music) by pausing/muting and resuming correctly.
- [ ] **Lifecycle Management**: WebSocket disconnects/reconnects when app goes to background/foreground.
- [ ] **Permissions**: Flow includes requesting Microphone permission (and handling denial) with appropriate usage descriptions in `app.json`.
- [ ] **UI Feedback**: Visual indicator when listening vs. speaking (and connecting state).

## Non-Functional Requirements
- **Battery**: Efficient audio capture/playback.
- **Smoothness**: No audio glitches/gaps between chunks.

## Linked ADRs
- ADR-008

## Impact Analysis Summary
Components touched: `frontend/react-native/components/VoiceChat.tsx`, `app.json` (permissions)
Workflows affected: Mobile functionality
Risks identified: Device specific audio issues (permissions, codecs).

## Test Strategy
- Manual verification on device/simulator.

## Rollback Plan
- Revert app updates.
