# INFRA-027: Core Voice Abstractions & Deepgram

## State

COMMITTED

## Linked Plan

INFRA-027

## Problem Statement

The current voice architecture (if any) or proposed new architecture needs to support multiple providers (e.g., Deepgram now, Local/Kokoro later). Hardcoding specific SDKs into the router makes this difficult.

## User Story

As a specific capability, I want abstract `STTProvider` and `TTSProvider` interfaces and a concrete Deepgram implementation, so that the underlying provider can be swapped without changing core business logic.

## Acceptance Criteria

- [ ] **Interface Definition**: `speech.interfaces.STTProvider` and `speech.interfaces.TTSProvider` are defined as abstract base classes (or Protocols).
- [ ] **Pure Abstractions**: The `speech.interfaces` module MUST NOT import any vendor SDKs (e.g. `deepgram`).
- [ ] **Async Interfaces**: All interface methods (e.g., `speak`, `listen`) must be `async` to support network I/O.
- [ ] **Deepgram Implementation**: `DeepgramSTT` and `DeepgramTTS` implement these interfaces using `deepgram-sdk`.
- [ ] **Secure Configuration**: Deepgram API Key is retrieved via `SecretManager` (or env vars), and the service fails gracefully (or refuses to start) if the key is missing.
- [ ] **Dependency Injection**: A simple `VoiceFactory` exists to return the configured provider.
- [ ] **Unit Tests**: Mocks prove that consumer code relies on the Interface, not the Deepgram client directly.
- [ ] **Observability**:
  - [ ] **Metrics**: Deepgram API calls (latency, errors) are tracked via `prometheus-client`.
  - [ ] **Tracing**: Requests are traced using OpenTelemetry.
  - [ ] **Logging**: All logs include correlation IDs and are PII-safe.
  - [ ] **Health Check**: Service reports connectivity status to Deepgram.

## Non-Functional Requirements

- **Extensibility**: Must allow future addition of `LocalSTT`/`LocalTTS` without refactoring consumers.
- **Performance**: Abstraction overhead must be negligible.

## Linked ADRs

- ADR-007

## Impact Analysis Summary

Components touched: `backend/speech/`, `backend/routers/`
Workflows affected: Voice interaction
Risks identified: None

## Test Strategy

- Unit tests for the container/factory.
- Unit tests for Deepgram wrappers (mocking the actual HTTP calls using `respx` or `unittest.mock`).
- **Interface Compliance**: Test that verifies `DeepgramSTT` strictly implements the `STTProvider` interface (e.g., `isinstance` check).

## Rollback Plan

- Revert code changes.
