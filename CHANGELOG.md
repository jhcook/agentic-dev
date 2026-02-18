# Changelog

## [Unreleased]

### Added

- **Multi-Agent Governance Panel via Google ADK** (INFRA-061):
  - Opt-in ADK-based multi-agent orchestration for the governance panel.
  - Configure with `panel.engine: adk` in `agent.yaml` or `--panel-engine adk` CLI flag.
  - 5 read-only tools for agents: `read_file`, `search_codebase`, `list_directory`, `read_adr`, `read_journey`.
  - Graceful fallback to legacy panel if `google-adk` is not installed or fails.
  - Install with: `pip install 'agent[adk]'`.
  - See ADR-029 for architecture decisions.

- **Interactive Preflight Repair** (INFRA-042):
  - Added `--interactive` flag to `agent preflight`.
  - Implemented `InteractiveFixer` service for identifying and repairing Story schema and governance violations.
  - Added AI-powered fix suggestions and automated verification loop.
  - Added File-based backup mechanism (replacing `git stash`) for safe rollbacks.
- **Improved Preflight Output & UX** (INFRA-056):
  - Added **Blocking Issues Summary** to clarify overall status before detailed panels.
  - Added **Interactive Secret Unlock**: Prompts to unlock Secret Manager if credentials are found but locked.
  - Added **GH Models Context Limit Handling**: Explicitly warns when prompts exceed 8k token limits (413 errors).
  - Added **Smart Content Truncation**: Automatically truncates large files in `InteractiveFixer` to fit context windows (simulating chunking).
  - Fixed duplicate output panels in interactive mode.
  - Optimized output verbosity.
- **Architectural Compliance**:
  - Moved credential validation to `AIService` (Core layer) to clean up CLI dependencies.
  - Relaxed security restrictions for internal agent development tools (`security.md`).
- **Bug Fixes**:
  - Fixed JSON escaping in test failure prompts (QA Prompt Injection).
  - Fixed "Invalid JSON" errors in preflight response parsing.
  - Fixed `LLM_PROVIDER` resolution ignoring `agent.yaml`.
  - Enforced credential validation for locked Secret Manager to prevent silent fallback.
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
- **Agent Sync Restoration** (INFRA-045):
  - Fixed `agent sync` CLI wiring regression.
  - Enforced authentication for remote sync operations (`pull`/`push`) via new `with_creds` decorator.
  - Added strict governance for CLI commands (ADR-017).
- **Multi-Backend Sync** (INFRA-054):
  - Updated `agent sync` to support multiple backends (Notion, Supabase) via `--backend` flag.
  - Added `--force` flag for overwriting remote or local state.
  - Implemented **Interactive Conflict Resolution** for handling content divergance.
  - Integrated `janitor` command with multi-backend support.
  - Added `agent sync init` command for bootstrapping synchronization environments.
  - Implemented **Self-Healing Sync** to detect and repair missing environments (e.g. Notion 404s).
- **Automated Branching for Implement Command** (INFRA-055):
  - Enhanced `agent implement` to enforce git hygiene.
  - Automatically creates and checks out feature branches (`STORY-ID/title`).
  - Blocks execution if on an incorrect branch or if git state is dirty.
