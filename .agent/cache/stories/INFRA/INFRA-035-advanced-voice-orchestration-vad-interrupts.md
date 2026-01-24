# INFRA-035: Advanced Voice Orchestration (VAD & Interrupts)

## State

COMMITTED

## Problem Statement

The current voice agent is "half-duplex" in feel: it speaks until finished, ignoring user input during playback. This feels unnatural. Users want to be able to interrupt ("barge in") the agent. Additionally, we need proper Voice Activity Detection (VAD) to know when the user has started speaking to trigger this interrupt.

## User Story

As a User, I want to be able to interrupt the agent by speaking, so that I can correct it or move the conversation forward without waiting for it to finish a long sentence.

## Acceptance Criteria

- [ ] **VAD Integration**: Implement VAD (e.g. Silero VAD or WebRTC VAD) on the incoming audio stream to detect speech start.
- [ ] **Interrupt Handler**: When speech is detected during TTS playback:
  - 1. Send "STOP" signal to TTS provider (cancel generation).
  - 1. Send "CLEAR_BUFFER" to client (stop playback).
  - 1. Update Agent state (inform it of interruption).
- [ ] **Turn-Taking**: Implement logic to handle "double talk" gracefully.

## Non-Functional Requirements

- **Latency**: Interruption must perceive as instantaneous (<200ms).
- **False Positives**: VAD must not trigger on background noise (keyboard typing, breathing).

## Linked ADRs

- ADR-009

## Impact Analysis Summary

Components touched: `VoiceOrchestrator`, `WebSocket Router`.
Workflows affected: Voice Chat.
Risks: VAD being too sensitive.

## Test Strategy

- **Simulation**: dedicated unit test feeding audio while "playing" flag is true.
- **Manual**: Speak while agent is talking.

## Rollback Plan

- Disable VAD/Interrupt feature flag.
