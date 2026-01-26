# INFRA-037: Additional Voice Providers (Google & Azure)

## State

COMMITTED

## Problem Statement

The Voice backend currently supports only Deepgram and Local (Kokoro) providers. To be a robust platform, we must support major cloud providers like Google Cloud Speech and Azure Cognitive Services, which offer different trade-offs in terms of quality, latency, and language support.

## User Story

As a Developer, I want to configure the agent to use Google or Azure for voice, so that I can choose the best provider for my specific region or quality requirements.

## Acceptance Criteria

- [ ] **Google Provider**: Implement `GoogleSTT` and `GoogleTTS` classes using `google-cloud-speech` and `google-cloud-texttospeech`. MUST use `SpeechAsyncClient`.
- [ ] **Azure Provider**: Implement `AzureSTT` and `AzureTTS` classes using `azure-cognitiveservices-speech`.
- [ ] **Factory Update**: Update `get_voice_providers()` to support `VOICE_PROVIDER=google` and `VOICE_PROVIDER=azure`. Consider a dynamic registry pattern.
- [ ] **Configuration**: Update `onboard` command to prompt for Azure Keys and Google Application Credentials (file path or JSON content). **WARNING**: Warn user to NEVER commit JSON keys.
- [ ] **Observability**: Ensure `voice.provider` attribute is added to all OpenTelemetry spans.

## Non-Functional Requirements

- **Abstraction**: New providers must strictly adhere to `STTProvider` and `TTSProvider` protocols.
- **Async**: Use async SDK methods (especially `SpeechAsyncClient` for Google) or `run_in_executor` to avoid blocking.
- **Streaming**: Support gRPC streaming API for low latency where possible.
- **Dependencies**: Pin strict versions for SDKs in `pyproject.toml` to avoid conflicts.

## Linked ADRs

- ADR-009

## Impact Analysis Summary

Components touched: `backend/speech/providers/`, `backend/speech/factory.py`.
Workflows affected: Voice Chat.
Risks: Dependency bloat (consider optional installs), Async IO blocking main loop, Credential mismanagement (keys in code).

## Test Strategy

- Integration tests using mocked SDK clients.
- **Automated Smoke Tests**: Run live provider tests ONLY if credentials exist in env (skip otherwise).
- **Chaos Testing**: Verify handling of Quota Exceeded and Network Timeouts.
- Manual verification with valid credentials.

## Rollback Plan

- Revert factory changes.
