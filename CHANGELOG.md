# Changelog

## [Unreleased]

### Added

- Implemented core orchestration logic for real-time voice interaction via WebSocket endpoint `/ws/voice`.
- Created `VoiceOrchestrator` class for managing audio processing, STT, agent interaction, and TTS.
- **MCP Integration**: Added support for Model Context Protocol (MCP).
- **GitHub MCP Support**: Integrated `@modelcontextprotocol/server-github` for interaction with GitHub repositories and issues.
- **mcp command**: Added `agent mcp start` and `agent mcp run` commands.
- **Onboarding**: Updated `agent onboard` to allow choosing between MCP and `gh` CLI.
