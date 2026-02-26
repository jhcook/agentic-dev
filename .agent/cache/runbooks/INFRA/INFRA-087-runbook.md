# INFRA-087: Terminal Console TUI

## State

ACCEPTED

## Goal Description

Build a Textual-based TUI (`agent console`) that provides a persistent, multi-turn conversation interface with the agent's AI providers. The console enables conversation-driven workflow management — invoking workflows (`/commit`, `/preflight`, `/implement`) and addressing roles (`@architect`, `@security`) within a shared conversation context. Supports token caching, streaming responses, multi-provider selection, and conversation persistence in SQLite.

## Linked Journeys

- JRN-072 (Terminal Console TUI Chat)

## Panel Review Findings

- **@Architect**: Clean layering — TUI package imports `AIService` and `TokenManager` but introduces no new API surface on core. `textual` isolated as optional dependency. SQLite reuses existing `agent.db` path from `config.cache_dir`.
- **@Security**: Conversation data stored locally only (`.agent/cache/`). No new network endpoints. Provider API keys pass through existing `AIService` credential flow. No PII risk beyond what the user types.
- **@QA**: Textual supports headless testing via `textual run --headless`. Session CRUD and token pruning are pure logic — fully unit-testable. Streaming needs a mock provider.
- **@Compliance**: License headers required on all new files. No new data processing — GDPR scope unchanged.
- **@Observability**: Session lifecycle events logged. OTel spans for AI completions already exist in `AIService.complete()`.
- **@Docs**: README update for `agent console`. CHANGELOG entry. `/help` command provides in-app documentation.

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Extract streaming logic from `AIService._try_complete()` into a `stream_complete()` generator method to avoid duplicating provider-specific streaming code in the TUI.

## Implementation Steps

### Dependency Management

#### [MODIFY] pyproject.toml

- Add `console` optional dependency group:

  ```
  console = [
      "textual>=0.80.0",
  ]
  ```

- Add `textual` to `[dependency-groups] dev` so it's available during development.

---

### Session & Conversation Layer

#### [NEW] src/agent/tui/**init**.py

- Empty init file with license header.

#### [NEW] src/agent/tui/session.py

- `ConversationSession` dataclass: `id: str`, `title: str`, `created_at: datetime`, `updated_at: datetime`, `provider: str`, `model: str | None`, `messages: list[dict]` (role/content pairs).
- `SessionStore` class backed by SQLite (`config.cache_dir / "console.db"`):
  - **@Security**: Create DB file with mode `0600` (user-only read/write).
  - `create_session() -> ConversationSession`
  - `get_session(session_id: str) -> ConversationSession`
  - `get_latest_session() -> ConversationSession | None`
  - `list_sessions() -> list[ConversationSession]` (ordered by `updated_at desc`)
  - `add_message(session_id, role, content)` — appends to messages, updates `updated_at`.
  - `delete_session(session_id)` — hard delete.
  - `rename_session(session_id, title)`
  - `auto_title(session_id, first_message)` — sets title from first ~60 chars of first user message.
  - **@Security**: Do NOT persist API keys or credentials in session — only provider *name*.
- `TokenBudget` class:
  - Takes `max_tokens: int` (from `query.yaml` `max_context_tokens`, default 8192).
  - `build_context(system_prompt: str, messages: list[dict]) -> tuple[str, list[dict]]` — returns system prompt + pruned messages list. Prunes oldest turns FIFO until total tokens ≤ budget, always keeping system prompt + last 2 turns.
  - Uses `token_manager.count_tokens()` from `agent.core.tokens`.
  - **@Observability**: Log when pruning occurs (turns pruned, tokens before/after).

---

### AIService Streaming

#### [MODIFY] src/agent/core/ai/service.py

- Add `stream_complete()` generator method to `AIService`:

  ```python
  def stream_complete(
      self,
      system_prompt: str,
      user_prompt: str,
      model: Optional[str] = None,
      temperature: Optional[float] = None,
  ) -> Generator[str, None, None]:
  ```

  - Same provider selection and fallback logic as `complete()`.
  - For `gemini`/`vertex`: yields `chunk.text` from `generate_content_stream()`.
  - For `anthropic`: yields `text` from `client.messages.stream()`.
  - For `openai`/`ollama`: uses `stream=True` on `chat.completions.create()`, yields `chunk.choices[0].delta.content`.
  - For `gh`: falls back to non-streaming (yields full response as single chunk, since `gh models run` doesn't support streaming).

---

### TUI Application

#### [NEW] src/agent/tui/styles.tcss

- Textual CSS stylesheet defining the layout:
  - `#chat-output`: top-left, scrollable, takes ~70% width.
  - `#sidebar`: right, ~30% width, split vertically.
  - `#workflow-list`: top-right panel.
  - `#role-list`: bottom-right panel.
  - `#input-box`: full-width bottom bar.
  - `#status-bar`: bottom status bar below input (**@Product**) — shows current provider, model, and token usage (e.g. `vertex | gemini-2.5-pro | 2.1k/8k tokens`).
  - Rich dark theme with accent colours matching the existing agent branding.
  - CSS comment-style license header (`/* ... */`).

#### [NEW] src/agent/tui/app.py

- `ConsoleApp(textual.App)` — the main application:
  - `compose()`: creates the layout with `RichLog` (chat output), `ListView` (workflows), `ListView` (roles), `Input` (chat input), `Footer` (status bar).
  - `on_mount()`:
    - Load workflows from `config.agent_dir / "workflows"` (parse YAML frontmatter for descriptions).
    - Load roles from `config.etc_dir / "agents.yaml"`.
    - Resume latest session via `SessionStore.get_latest_session()`.
    - **@Product**: On first-ever launch (no sessions exist), display a welcome message with key shortcuts (`Tab` to switch panels, `/help` for commands).
    - **@Security**: Show one-time disclaimer: "Conversations are stored locally in `.agent/cache/console.db`".
  - Key bindings: `Tab` cycles focus, `Escape` exits modal dialogs.
  - **@Product**: Status bar updates after each message showing: current provider, model, token usage.
  - `on_input_submitted()`:
    - Parse input for commands (`/help`, `/quit`, `/new`, `/conversations`, `/delete`, `/clear`, `/provider`, `/model`, `/rename`).
    - Parse for `/<workflow>` prefix → load workflow `.md` content into system prompt augmentation.
    - Parse for `@<role>` prefix → load role YAML from `agents.yaml` into system prompt augmentation.
    - Otherwise: plain chat message.
    - Call `stream_complete()` via `run_worker()` (Textual async worker) and append chunks to `RichLog`.
    - **@QA**: On streaming disconnect/error, display partial content + error message — do not crash.
    - Persist message to `SessionStore`.
  - `action_quit()`: persist state, exit.
  - **@Observability**: Log `console.session.start`, `console.session.end`, `console.session.duration`.

#### [NEW] src/agent/tui/commands.py

- Command dispatcher: parses `/command [args]` patterns.
- Registered commands:
  - `/help` — writes formatted help table to chat output.
  - `/quit` — triggers `app.exit()`.
  - `/new` — creates new session, clears chat.
  - `/conversations` — lists sessions in chat output with selectable indices.
  - `/delete [id]` — prompts "Are you sure?" via inline confirmation.
  - `/clear` — clears chat display (history preserved in DB).
  - `/provider [name]` — calls `ai_service.set_provider()` or shows status.
  - `/model [name]` — sets model override for session.
  - `/rename [title]` — renames current conversation.

---

### CLI Entry Point

#### [NEW] src/agent/commands/console.py

- **@Architect (ADR-028)**: Command MUST be synchronous `def`, not `async def`.
- Typer command function:

  ```python
  def console(
      provider: str = typer.Option(None, "--provider",
          help="Force AI provider (gh, gemini, vertex, openai, anthropic, ollama)"),
  ):
  ```

  - If `provider` is set, call `ai_service.set_provider(provider)`.
  - Import and run `ConsoleApp` from `agent.tui.app`.
  - Wrapped in try/except for clean error messages if `textual` is not installed.

#### [MODIFY] src/agent/main.py

- Add import: `from agent.commands import console as console_cmd`
- Register command: `app.command(name="console")(console_cmd.console)`

---

### Documentation

#### [MODIFY] CHANGELOG.md

- Add INFRA-087 entry under `## [Unreleased]`:

  ```
  ### Added
  - `agent console` — Interactive terminal console with persistent conversations,
    streaming AI responses, workflow/role sidebars, and token caching (INFRA-087).
  ```

#### [MODIFY] README.md

- Add `agent console` to the commands table with description.

#### [NEW] docs/console.md

- **@Docs**: Dedicated usage guide covering:
  - Layout diagram (ASCII art of 4-pane layout).
  - All `/commands` with examples.
  - Keyboard shortcuts (`Tab`, arrow keys, `Enter`, `Escape`).
  - Workflow/role invocation examples.
  - Provider switching (`--provider` flag + `/provider` command).
  - Token caching behaviour and configuration.
  - README should link to this page.

## Verification Plan

### Automated Tests

#### [NEW] tests/tui/test_session.py

- Test `SessionStore` CRUD: create, get, list, delete, rename, auto_title.
- Test `TokenBudget.build_context()`: verify FIFO pruning preserves system prompt + last turns.
- **@QA**: Token pruning edge cases: (a) single-message conversation (no pruning), (b) system prompt alone exceeds budget (error path), (c) exactly-at-budget boundary.
- Test message persistence: add messages, reload session, verify messages restored.
- Test SQLite file is created with `0600` permissions.
- Run: `PYTHONPATH=.agent/src .venv/bin/pytest .agent/tests/tui/test_session.py -v`

#### [NEW] tests/tui/test_commands.py

- Test command parsing: `/help`, `/quit`, `/new`, `/provider vertex`, `/model gemini-2.5-pro`, unknown commands.
- Test workflow prefix detection: `/commit some message` → extracts workflow `commit` + message.
- Test role prefix detection: `@security review auth` → extracts role `security` + message.
- Run: `PYTHONPATH=.agent/src .venv/bin/pytest .agent/tests/tui/test_commands.py -v`

#### [NEW] tests/tui/test_stream.py

- Test `AIService.stream_complete()` with mocked Gemini/OpenAI/Anthropic clients.
- Verify it yields chunks and full concatenation matches expected response.
- **@QA**: Test streaming disconnect mid-response — verify partial content preserved and error displayed (no crash).
- Run: `PYTHONPATH=.agent/src .venv/bin/pytest .agent/tests/tui/test_stream.py -v`

### Manual Verification

- [ ] Run `agent console` — verify TUI launches with 4-pane layout.
- [ ] Type a message → verify streaming response appears in chat output.
- [ ] Press `Tab` → verify focus cycles: input → workflows → roles → input.
- [ ] Select a workflow with arrow keys + Enter → verify `/workflow` inserted into input.
- [ ] Send `/help` → verify command list appears.
- [ ] Send `/new` → verify new conversation started.
- [ ] Send `/conversations` → verify conversation list shown.
- [ ] Send `/delete` → verify "Are you sure?" confirmation.
- [ ] Send `/quit` → verify clean exit.
- [ ] Re-run `agent console` → verify last conversation is resumed.
- [ ] Run `agent console --provider anthropic` → verify Anthropic is the active provider.
- [ ] Send `/provider` → verify current provider and available providers shown.

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated
- [ ] README.md updated

### Observability

- [ ] Logs are structured and free of PII
- [ ] OTel spans from existing `AIService.complete()` cover console completions

### Testing

- [ ] Unit tests passed
- [ ] Integration tests passed

## Copyright

Copyright 2026 Justin Cook
