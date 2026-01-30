# Changelog

## [Unreleased]

### Added

- **Interactive Preflight Repair** (INFRA-042):
  - Added `--interactive` flag to `agent preflight`.
  - Implemented `InteractiveFixer` service for identifying and repairing Story schema and governance violations.
  - Added AI-powered fix suggestions and automated verification loop.
  - Added File-based backup mechanism (replacing `git stash`) for safe rollbacks.
- **Voice Agent Integration for Preflight** (INFRA-039):
  - Added `AGENT_VOICE_MODE` detection to optimize CLI output for speech-to-text interfaces.
  - Enabled hands-free interactive repair via voice commands.
- **Improved CLI Robustness**:
  - Restored `agent help` command regression.
  - Implemented PTY support for `agent preflight` in Voice Mode to fix output buffering and visible errors.

- Implemented core orchestration logic for real-time voice interaction via WebSocket endpoint `/ws/voice`.
- Created `VoiceOrchestrator` class for managing audio processing, STT, agent interaction, and TTS.
- **Integrated LangGraph for intelligent conversational agent in voice orchestrator** (INFRA-029)
  - Configurable LLM provider support (OpenAI, Anthropic, Gemini) via `agent config` (using `.agent/etc/voice.yaml`)
  - Voice-optimized system prompt (brief, conversational responses)
  - Streaming responses for low-latency interactions
  - Conversation checkpointing and session persistence
  - Input sanitization to prevent prompt injection attacks
  - Rate limiting (20 requests/minute per session)
  - Observability: Prometheus metrics, OpenTelemetry tracing, structured logging
- **MCP Integration**: Added support for Model Context Protocol (MCP).
- **GitHub MCP Support**: Integrated `@modelcontextprotocol/server-github` for interaction with GitHub repositories and issues.
- **mcp command**: Added `agent mcp start` and `agent mcp run` commands.
- **Onboarding**: Updated `agent onboard` to allow choosing between MCP and `gh` CLI.
- **Improved Voice Agent Process Management** (INFRA-041):
  - Real-time streaming of subprocess output (e.g. `npm audit`, `preflight`) via EventBus.
  - **Interactive Shell**: Support for running interactive commands via voice.
  - **Thread Safety**: Implemented thread storage for EventBus.
  - **Strict Secrets**: Removed environment variable fallback for API keys to enforce secure storage.
- **Additional Voice Providers** (INFRA-037):
  - Added support for **Google Cloud Speech** (Async STT/TTS).
  - Added support for **Azure Speech Services** (STT/TTS).
  - Updated `agent onboard` to securely prompt and encrypt keys for new providers.
  - Refactored voice factory to use a dynamic registry pattern.
