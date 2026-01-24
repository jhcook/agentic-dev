# INFRA-037: Additional Voice Providers (Google & Azure)

## State

COMMITTED

## Problem Statement

The Voice backend currently supports only Deepgram and Local (Kokoro) providers. To be a robust platform, we must support major cloud providers like Google Cloud Speech and Azure Cognitive Services, which offer different trade-offs in terms of quality, latency, and language support.

## User Story

As a Developer, I want to configure the agent to use Google or Azure for voice, so that I can choose the best provider for my specific region or quality requirements.

## Acceptance Criteria

- [ ] **Google Provider**: Implement `GoogleSTT` and `GoogleTTS` classes using `google-cloud-speech` and `google-cloud-texttospeech`.
- [ ] **Azure Provider**: Implement `AzureSTT` and `AzureTTS` classes using `azure-cognitiveservices-speech`.
- [ ] **Factory Update**: Update `get_voice_providers()` to support `VOICE_PROVIDER=google` and `VOICE_PROVIDER=azure`.
- [ ] **Configuration**: Update `onboard` command to prompt for Google Application Credentials and Azure Keys.

## Non-Functional Requirements

- **Abstraction**: New providers must strictly adhere to `STTProvider` and `TTSProvider` protocols.
- **Async**: Use async SDK methods or `run_in_executor` to avoid blocking.

## Linked ADRs

- ADR-009

## Impact Analysis Summary

Components touched: `backend/speech/providers/`, `backend/speech/factory.py`.
Workflows affected: Voice Chat.
Risks: Dependency bloat. Consider making these optional installs?

## Test Strategy

- Integration tests using mocked SDK clients.
- Manual verification with valid credentials.

## Rollback Plan

- Revert factory changes.
