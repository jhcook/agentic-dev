# Changelog

## [Unreleased]

### Added

- **Terminal Console TUI** (INFRA-087):
  - New `agent console` command launches an interactive terminal UI for AI-assisted development.
  - Textual-based layout with chat panel, workflow sidebar, and role sidebar.
  - Persistent conversation sessions stored in local SQLite (`console.db`) with `0600` permissions.
  - Token-by-token streaming via `AIService.stream_complete()` for Gemini, Vertex, Anthropic, OpenAI, and Ollama.
  - Built-in commands: `/help`, `/new`, `/conversations` (`/history`), `/delete`, `/rename`, `/clear`, `/provider`, `/model`, `/quit`.
  - Click-to-insert workflow (`/commit`, `/preflight`, etc.) and role (`@architect`, `@security`, etc.) from the sidebar.
  - Agent disconnect recovery modal with Retry / Switch Provider / Cancel options.
  - FIFO token budget pruning to stay within context window limits.
  - Install with: `pip install 'agent[console]'`.

- **Console Agentic Tool Capabilities** (INFRA-088):
  - Agentic tool-calling loop with native function calling for Gemini, Vertex, OpenAI, and Anthropic.
  - `LocalToolClient` adapter exposes 9 local tools (5 read-only + 4 interactive) to the `AgentExecutor` without requiring an MCP server.
  - Interactive tools: `read_file`, `edit_file`, `run_command`, `find_files`, `grep_search`.
  - Read-only tools: `search_codebase`, `list_directory`, `read_adr`, `read_journey`.
  - Non-tool-calling providers (Ollama, GH CLI) fall back to simple `stream_complete` text streaming.
  - `--model` CLI flag: `agent console --model gemini-2.5-flash` to override the default model.
  - **Model Selector Panel** in the sidebar — curated list of preferred models across all configured providers. Click to switch provider and model mid-conversation.
  - `run_command` sandboxing: path traversal, absolute paths outside repo, and dangerous commands are blocked.
  - Disconnect recovery, max-iteration limits, and structured error handling for tool failures.
  - See ADR-040 for architecture details.

- **Console UX Enhancements** (INFRA-088):
  - **Command history**: ↑/↓ arrow keys navigate previously submitted commands, with stash/restore of current input.
  - **`/search <query>`**: Case-insensitive text search in the output panel. `n` and `r` keys navigate between matches.
  - **`/tools`**: List available agentic tools.
  - **Real-time command output**: `run_command` output streams line-by-line to the chat panel via `on_output` callback (visible during `/preflight`, etc.).
  - **Text width fix**: Markdown output now wraps correctly within the chat container instead of overflowing to terminal width.
  - **`/copy`**: Copy full chat content to clipboard. Also available via Ctrl+Y keyboard shortcut.
  - **`/provider` fuzzy matching**: `/provider gem` matches `gemini`. No args opens a scrollable picker modal.
  - **`/model` fuzzy matching**: `/model gemini pro` matches `gemini-2.5-pro`. No args opens a scrollable picker. Matching priority: exact → prefix → substring → word overlap.
  - **Model propagation**: Selected model is explicitly passed through `AgentExecutor` to `llm.complete()`, bypassing smart routing.

### Fixed

- **ReAct JSON parser hardening** (INFRA-088):
  - Replaced fragile regex with brace-counting `_extract_json()` helper for reliable nested JSON extraction.
  - Implemented 3-strategy parsing: Action marker → code fences → any-JSON block.
  - Fixes `/preflight` immediately passing without execution (was silently falling back to `AgentFinish`).

- **Token budget session destruction** (INFRA-088):
  - Console was using `query.yaml` `max_context_tokens: 8192` (designed for `agent query`, not interactive console). After 8192 tokens, sessions would crash or lose all history.
  - Added `_get_model_context_window()` that reads per-model `context_window` from `router.yaml` (Gemini 2.5 Pro: 2M, Flash: 1M, GPT-4o: 128K, Claude: 200K).
  - Default raised from 8192 to 128,000 tokens.
  - Added `ValueError` catch around `build_context()` so budget overflow falls back to the latest message instead of crashing the worker thread.


- **Console blank screen on launch** (INFRA-088):
  - `get_latest_session()` now prefers sessions with messages over empty orphan sessions.
  - Welcome message displays when the loaded session has no conversation history.
  - Assistant responses render as Markdown blocks instead of fragmented per-token lines.

- **Console streaming architecture** (INFRA-088):
  - `_do_stream` uses `@work(thread=True)` for correct Textual threading model (`call_from_thread` requires a separate OS thread).
  - Replaced `MCPClient` (MCP server connection) with `LocalToolClient` (local Python tools) for console tool execution.
  - Error logging now includes `exc_info=True` for full tracebacks.

- **Console stream routing regression** (INFRA-088):
  - Regular chat was incorrectly routed through the agentic ReAct loop for all function-calling providers. Fixed with `use_tools` flag: only workflow and role invocations use the agentic path.
  - `on_output` callback was not wired to `run_agentic_loop`, causing `/preflight` to appear frozen. Now streams real-time command output.
  - Replaced `asyncio.run()` with `asyncio.new_event_loop()` to avoid conflicting with Textual's event loop.
  - 10 new regression tests in `test_stream_routing.py` covering routing, retry preservation, command history, and search.

### Added

- **Preflight INCONCLUSIVE Detection**:
  - `agent preflight` now detects when all governance agents fail (e.g. expired credentials) and reports `INCONCLUSIVE` with a provider-specific remediation hint instead of falsely reporting `✅ Passed`.

- **NotebookLM Integration Guide**:
  - New `.agent/docs/notebooklm.md` documentation covering MCP server configuration, authentication (`agent mcp auth notebooklm`), sync commands (`agent sync notebooklm`), security considerations, and troubleshooting.

- **Ollama Local AI Provider** (INFRA-017):
  - Added Ollama as a self-hosted AI provider using the OpenAI-compatible API.
  - Health check on startup with graceful skip if Ollama is not running.
  - Localhost-only security guard on `OLLAMA_HOST` to prevent data exfiltration.
  - Configurable via `OLLAMA_HOST` (default: `http://localhost:11434`) and `OLLAMA_MODEL` (default: `llama3`).
  - Added `local` → `light` tier alias in the Smart Router for Ollama model selection.
  - Ollama participates in the fallback chain: `gh → gemini → vertex → openai → anthropic → ollama`.

- **NotebookLM Authentication Remediation** (INFRA-078):
  - Refactored `agent mcp auth notebooklm` to include an explicit GDPR consent prompt for automatic cookie extraction.
  - Cookies are now securely stored in the OS-native Keychain via `SecretManager` instead of a plaintext file.
  - Properly documented and improved the existing `--no-auto-launch` flag to print manual extraction instructions (this flag is explicitly present and active, NOT removed).
  - Built-in `--file` and `--auto` flags are now properly documented.
  - Added `--clear-session` flag to clear saved session cookies.
  - Added new `agent sync notebooklm` command and the `--reset` and `--flush` flags for database state management.
  - Pinned `browser-cookie3` to version `0.20.1` and verified its LGPL-3.0 license.
  - Re-introduced OpenTelemetry tracing spans and structured logging for observability.

- **Source Code Context for Runbook Generation** (INFRA-066):
  - `agent new-runbook` now includes source file tree and code outlines in AI prompts.
  - Produces runbooks with accurate file paths and SDK usage matching the actual codebase.
  - Configurable character budget via `AGENT_SOURCE_CONTEXT_CHAR_LIMIT` env var (default: 8000).
  - Graceful degradation when `src/` directory is absent.

- **Align `/impact` Workflow with CLI** (INFRA-068):
  - Simplified `/impact` workflow from 98-line manual process to CLI-first instructions calling `agent impact`.
  - Improved structured output with markdown formatting, component grouping, and blast-radius risk summary.
  - Added DEBUG logging for dependency graph size and AI prompt character count.
  - Added 5 unit tests for `agent impact` (no-changes, static output, update-story, base branch, JSON).

- **Align `/panel` Workflow with CLI** (INFRA-069):
  - Simplified `/panel` workflow from 59-line manual simulation to CLI-first instructions calling `agent panel`.
  - Added negative test for missing story ID scenario.

- **Align `/pr` Workflow with CLI** (INFRA-070):
  - Simplified `/pr` workflow from 73-line manual process to CLI-first instructions calling `agent pr`.
  - Added `--skip-preflight` flag with timestamped audit logging for SOC2 compliance.
  - PR body now scrubbed via `scrub_sensitive_data()` in all modes (not just AI).
  - Governance status in PR body reflects whether preflight was skipped.
  - Added 4 unit tests for `agent pr` (title format, skip-preflight, gh-not-found, body scrubbing).

- **Create `agent review-voice` CLI Command** (INFRA-072):
  - New `agent review-voice` command fetches last voice session and runs AI-powered UX analysis.
  - Analyzes sessions across latency, accuracy, tone, and interruption categories.
  - Structured output with per-category ratings and concrete recommendations.
  - Session data scrubbed via `scrub_sensitive_data()` before AI submission (GDPR Art. 6(1)(f)).
  - Simplified `/review-voice` workflow from 25-line manual process to CLI-first.
  - Added 4 unit tests for review-voice command.

- **Post-Apply Governance Gates for Implement Command** (INFRA-067):
  - `agent implement --apply` now runs security scan, QA validation, and documentation check after code is applied.
  - New composable `gates.py` module with `run_security_scan()`, `run_qa_gate()`, `run_docs_check()`.
  - Externalized security patterns via `.agent/etc/security_patterns.yaml`.
  - Configurable test command via `test_command` in `agent.yaml` (default: `make test`).
  - `--skip-tests` and `--skip-security` flags with timestamped audit logging.
  - Structured `[PHASE]` output with PASSED/BLOCKED verdict and timing.
  - Auto-stages all modified files (implementation, story, runbook) after governance gates pass.
  - Relaxed dirty-state check: warns on story branches instead of blocking (only blocks on `main`).

- **Vertex AI Provider Support** (INFRA-065):
  - New `provider: vertex` option in `agent.yaml` for Google Vertex AI with ADC authentication.
  - Higher rate limits and production-grade scalability vs free-tier Gemini.
  - Shared `_build_genai_client()` factory for Gemini and Vertex (same SDK, different auth).
  - Vertex participates in the fallback chain: `gh → gemini → vertex → openai → anthropic`.
  - Set `GOOGLE_CLOUD_PROJECT` (and optionally `GOOGLE_CLOUD_LOCATION`) to enable.
  - See `.agent/docs/getting_started.md` for setup instructions.

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

## Copyright

Copyright 2024-2026 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
