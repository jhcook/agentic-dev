# INFRA-038: Advanced Voice Capabilities

## State

APPROVED

## Related Story

INFRA-035
INFRA-036
INFRA-037

## Linked ADRs

- ADR-009

## Summary

Transform the basic voice integration into a robust, interactive, and multi-provider agent platform. This plan addresses key user needs for control ("barge-in"), capability (tools), and flexibility (providers).

## Objectives

- **Control:** Allow users to interrupt the specific Agent (VAD + Interrupt Logic).
- **Intelligence:** Enable the Voice Agent to use tools and remember context.
- **Flexibility:** Expand beyond 1-2 providers to support Cloud Giants (Google, Azure).

## Milestones

- **M1: Control (INFRA-035)**
  - Implement Voice Activity Detection (silero/webrtcvad).
  - Implement TTS Interrupt/Stop signals.
- **M2: Intelligence (INFRA-036)**
  - Integrate Tools into `VoiceOrchestrator` agent loop.
  - Add persistent Checkpointer (SQLite).
- **M3: Flexibility (INFRA-037)**
  - Add Google Cloud STT/TTS.
  - Add Azure Speech Services.

## Risks & Mitigations

- **Risk:** VAD False Positives cutting off the agent.
  - **Mitigation:** Tunable silence thresholds involved.
- **Risk:** Tool latency causing long silences.
  - **Mitigation:** Filler audio ("Let me check that...").

## Verification

- **Automated:**
  - Mocked interaction tests for tool use.
- **Manual:**
  - "Barge-in" stress test.
  - Multi-turn conversation test across restarts.
