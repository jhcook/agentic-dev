# Changelog

## [Unreleased]

### Added

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
