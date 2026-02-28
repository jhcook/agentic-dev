# Copyright 2026 Justin Cook
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Console TUI Application (INFRA-087).

Provides a persistent, multi-turn conversation interface with the agent's
AI providers, workflow/role discovery, and disconnect recovery.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Input,
    Label,
    ListItem,
    ListView,
    OptionList,
    Static,
)
from textual.containers import VerticalScroll
from textual.widgets.option_list import Option

class SelectionLog(VerticalScroll):
    """A replacement for RichLog that holds Static widgets to allow for native text selection."""
    
    def write(self, renderable: Any, scroll_end: bool = False) -> None:
        widget = Static(renderable)
        widget._search_text = getattr(renderable, "markup", str(renderable))
        self.mount(widget)
        if scroll_end:
            self.scroll_end(animate=False)

    def clear(self) -> None:
        self.query("*").remove()

from agent.tui.commands import (
    InputType,
    ParsedInput,
    discover_roles,
    discover_workflows,
    format_help_text,
    parse_input,
)
from agent.tui.session import ConversationSession, Message, SessionStore, TokenBudget

logger = logging.getLogger(__name__)

# System prompt builder — constructs context-rich prompt at runtime
def _build_system_prompt() -> str:
    """Build a system prompt modeled after the voice agent's depth."""
    from agent.core.config import config

    repo_root = str(config.repo_root)
    repo_name = config.repo_root.name

    # Read the actual license header template
    license_header = ""
    try:
        license_path = config.templates_dir / "license_header.txt"
        if license_path.exists():
            license_header = license_path.read_text().strip()
    except Exception:
        pass

    prompt = (
        f"You are an expert agentic development assistant embedded in the "
        f"**{repo_name}** repository at `{repo_root}`.\n\n"
        "## Formatting Rules\n"
        "1. **Be Concise**: Keep responses short unless asked for detail.\n"
        "2. **Think Before Acting**: Use the ReAct format to `Thought:` about what to do, then use an `Action:`.\n"
        "3. **Direct Answers**: When providing the Final Answer, be direct and assertive. No filler. Do not narrate your actions (e.g., avoid \"I will now...\", \"I have...\").\n"
        "4. **No Apologies**: If an error is pointed out, acknowledge it briefly and provide the correction. Do not apologize.\n"
        "5. **Infer Context**: If asked about the current state, proactively "
        "check git branches, logs, or status files without asking permission.\n"
        "6. **Technical Output**: All technical lists (files, git status, logs) "
        "MUST be inside markdown code blocks.\n"
        "7. **Never Guess**: When asked about code, read the file first.\n"
        "8. Assume the role of Engineering Lead, Developer, or Release "
        "Coordinator as needed.\n\n"
        "## Project Layout\n"
        "```\n"
        f"{repo_name}/\n"
        "├── .agent/              # Agent configuration & artifacts\n"
        "│   ├── src/agent/       # Agent CLI source (Python/Typer)\n"
        "│   ├── tests/           # Test suite (pytest)\n"
        "│   ├── workflows/       # Executable workflow definitions (.md)\n"
        "│   ├── etc/             # Config (agent.yaml, agents.yaml)\n"
        "│   ├── cache/           # Stories, runbooks, journeys\n"
        "│   ├── adrs/            # Architecture Decision Records\n"
        "│   └── docs/            # Project documentation\n"
        "├── CHANGELOG.md\n"
                "└── README.md\n"
        "```\n\n"
        "## Slash Commands & Workflows\n"
        "1. **Workflow Priority**: For any message starting with `/` (e.g., `/commit`, `/story`), you MUST first use `read_file` to retrieve the corresponding workflow definition from `.agent/workflows/[command].md`.\n"
        "2. **Strict Adherence**: Follow the steps in the workflow precisely. Assumptions lead to regressions.\n"
        "3. **Role Adoption**: If the workflow specifies a role (e.g., @Architect, @Security), adopt that persona's priorities and checks.\n\n"
        "## Tool Creation\n"
        "You are **self-evolving**. If you lack a tool, build one:\n"
        "1. Write the tool function with `edit_file` to "
        "`.agent/src/agent/core/adk/tools.py`.\n"
        "2. Add it to `TOOL_SCHEMAS` and `TOOL_FUNCTIONS` in the same file.\n"
        "3. It will be available in the next agentic invocation.\n"
        "4. **Restricted Modules**: Avoid `subprocess`, `os.system`, `exec`, "
        "`eval` unless absolutely necessary — use `run_command` instead.\n\n"
        "## Environment Management\n"
        "- Use tools for repo manipulation.\n"
        "- Use `run_command` for environment setup, package installation, "
        "running tests, and git operations.\n"
        "- Always verify repo state with `run_command('git status')` before "
        "and after significant changes.\n"
        "- Proactively check git branches and status when context is missing.\n\n"
    )

    # Add license header instructions if template exists
    if license_header:
        prompt += (
            "## License Headers\n"
            "**CRITICAL**: When creating or editing source files, use the EXACT "
            "project license header below. Do NOT invent or modify copyright text.\n\n"
            "For Python files, prefix each line with `# `:\n"
            "```\n"
            + "\n".join(f"# {line}" if line.strip() else "#" for line in license_header.splitlines())
            + "\n```\n\n"
            "For CSS/JS files, wrap in `/* */` block comments.\n"
            "For Markdown, use the raw text at the top of the file.\n\n"
                        "The template lives at `.agent/templates/license_header.txt`. You can also call `agent.core.utils.get_full_license_header(prefix)` programmatically to get the formatted header for any comment style.\n\n"
            "## Interaction Style\n"
            "- **Assertive & Neutral**: Use a professional, engineering-focused tone. \n"
            "- **Action-Oriented**: Focus on state changes and verification.\n"
            "- **Minimalist**: Use the smallest possible tool calls to achieve the goal.\n"
        )

    return prompt


# Cache the prompt after first build
_CACHED_SYSTEM_PROMPT: str | None = None


def _get_system_prompt() -> str:
    """Return the system prompt, building and caching on first call."""
    global _CACHED_SYSTEM_PROMPT
    if _CACHED_SYSTEM_PROMPT is None:
        _CACHED_SYSTEM_PROMPT = _build_system_prompt()
    return _CACHED_SYSTEM_PROMPT

WELCOME_MESSAGE = """\
[bold cyan]╭─── Agent Console ───╮[/bold cyan]

Welcome to the Agent Console! This is your conversation-driven
interface for managing the agent.

[bold]🔧 Agentic Tools Enabled[/bold] — The AI can read/edit files,
run commands, and search code within this repository.
Type [bold]/tools[/bold] to see available tools and status.

[bold yellow]⚠ Data Notice:[/bold yellow] File contents, command outputs, and
search results from tool use are sent to the external AI provider
you have configured. Do not use tools on files containing secrets
or sensitive personal data.

  [bold]Ctrl+C / Q[/bold] Exit the console
  [bold]Ctrl+Y[/bold]       Copy chat to clipboard
  [bold]/help[/bold]     Show all commands

[dim]Conversations are stored locally in .agent/cache/console.db[/dim]
"""


# Curated list of preferred models across providers.
# Each entry: (display_name, provider, model_id)
PREFERRED_MODELS = [
    ("Gemini 2.5 Pro",   "gemini",    "gemini-2.5-pro"),
    ("Gemini 2.5 Flash", "gemini",    "gemini-2.5-flash"),
    ("Gemini 2.0 Flash", "vertex",    "gemini-2.0-flash"),
    ("GPT-4o",           "openai",    "gpt-4o"),
    ("GPT-4.1",          "openai",    "gpt-4.1"),
    ("Claude Sonnet 4",  "anthropic", "claude-sonnet-4-20250514"),
    ("Claude Opus 4",    "anthropic", "claude-opus-4-20250514"),
    ("Ollama (Local)",   "ollama",    None),  # uses OLLAMA_MODEL env default
]

class DisconnectModal(ModalScreen[str]):
    """Modal shown when the AI provider disconnects mid-stream.

    Offers Retry / Switch Provider / Cancel, similar to Antigravity's
    disconnect recovery flow.
    """

    DEFAULT_CSS = """
    DisconnectModal {
        align: center middle;
    }
    #disconnect-dialog {
        width: 60;
        height: auto;
        max-height: 14;
        border: thick $error;
        background: $surface;
        padding: 1 2;
    }
    #disconnect-dialog Static {
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    #disconnect-actions {
        layout: horizontal;
        align: center middle;
        height: 3;
    }
    #disconnect-actions Button {
        margin: 0 1;
    }
    """

    def __init__(self, error_msg: str = "") -> None:
        super().__init__()
        self.error_msg = error_msg

    def compose(self) -> ComposeResult:
        with Container(id="disconnect-dialog"):
            yield Static(
                f"[bold red]⚠ Provider Disconnected[/bold red]\n\n"
                f"[dim]{self.error_msg[:120]}[/dim]"
            )
            with Horizontal(id="disconnect-actions"):
                yield Button("Retry", variant="primary", id="btn-retry")
                yield Button("Switch Provider", variant="warning", id="btn-switch")
                yield Button("Cancel", variant="error", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        action_map = {
            "btn-retry": "retry",
            "btn-switch": "switch",
            "btn-cancel": "cancel",
        }
        self.dismiss(action_map.get(event.button.id, "cancel"))


class ConfirmDeleteModal(ModalScreen[bool]):
    """Modal to confirm conversation deletion."""

    DEFAULT_CSS = """
    ConfirmDeleteModal {
        align: center middle;
    }
    #confirm-dialog {
        width: 50;
        height: auto;
        border: thick $warning;
        background: $surface;
        padding: 1 2;
    }
    #confirm-actions {
        layout: horizontal;
        align: center middle;
        height: 3;
    }
    #confirm-actions Button {
        margin: 0 1;
    }
    """

    def __init__(self, title: str = "") -> None:
        super().__init__()
        self._title = title

    def compose(self) -> ComposeResult:
        with Container(id="confirm-dialog"):
            yield Static(
                f"[bold yellow]Delete conversation?[/bold yellow]\n\n"
                f'"{self._title}"\n\n'
                f"[dim]This action cannot be undone.[/dim]"
            )
            with Horizontal(id="confirm-actions"):
                yield Button("Delete", variant="error", id="btn-confirm-yes")
                yield Button("Cancel", variant="primary", id="btn-confirm-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-confirm-yes")


class PickerModal(ModalScreen[str]):
    """Scrollable selection list for providers/models."""

    DEFAULT_CSS = """
    PickerModal {
        align: center middle;
    }
    #picker-dialog {
        width: 60;
        max-height: 24;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #picker-title {
        text-align: center;
        margin-bottom: 1;
    }
    #picker-list {
        height: auto;
        max-height: 16;
    }
    """

    def __init__(self, title: str, items: list[tuple[str, str]]) -> None:
        """Args: title, items as list of (id, display_label)."""
        super().__init__()
        self._title = title
        self._items = items  # [(value, label), ...]

    def compose(self) -> ComposeResult:
        with Container(id="picker-dialog"):
            yield Static(f"[bold]{self._title}[/bold]", id="picker-title")
            ol = OptionList(id="picker-list")
            for value, label in self._items:
                ol.add_option(Option(label, id=value))
            yield ol

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        self.dismiss(event.option.id)

    def key_escape(self) -> None:
        self.dismiss("")


class ConsoleApp(App):
    """The main Agent Console TUI application."""

    CSS_PATH = "styles.tcss"
    BINDINGS = [
        Binding("tab", "focus_next", "Next Panel", show=False),
        Binding("shift+tab", "focus_previous", "Previous Panel", show=False),
        Binding("escape", "dismiss_modal", "Dismiss", show=False),
        Binding("ctrl+c", "quit", "Quit", show=False, priority=True),
        Binding("ctrl+q", "quit", "Quit", show=False),
        Binding("ctrl+y", "copy", "Copy", show=False),
    ]

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._initial_provider = provider
        self._initial_model = model
        self._store: Optional[SessionStore] = None
        self._session: Optional[ConversationSession] = None
        self._workflows: Dict[str, str] = {}
        self._roles: Dict[str, str] = {}
        self._token_budget: Optional[TokenBudget] = None
        self._is_first_launch = False

        # Streaming state for disconnect recovery
        self._last_system_prompt: str = ""
        self._last_user_prompt: str = ""
        self._partial_response: str = ""

        # Command history (↑/↓ arrow navigation)
        self._command_history: list[str] = []
        self._history_index: int = -1
        self._history_stash: str = ""  # saves current input when navigating

        # Search state (/search, n=next, r=reverse)
        self._search_query: str = ""
        self._search_matches: list[Any] = []  # SelectionLog widgets
        self._search_match_index: int = -1

        # Plain text buffer for copy-to-clipboard
        self._chat_text: list[str] = []
        self._streaming_text = ""

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-area"):
            with Container(id="chat-container"):
                yield SelectionLog(id="chat-output")
                # Active streaming widget (Static) to avoid SelectionLog line fragmentation
                yield Static("", id="assistant-stream", markup=False, expand=True)
                yield SelectionLog(id="exec-output")
            with Vertical(id="sidebar"):
                with Container(id="workflow-panel"):
                    yield Static("Workflows")
                    yield ListView(id="workflow-list")
                with Container(id="role-panel"):
                    yield Static("Roles")
                    yield ListView(id="role-list")
                with Container(id="model-panel"):
                    yield Static("Models")
                    yield ListView(id="model-list")
        yield Static("", id="status-bar")
        yield Input(
            placeholder="Type a message or /help for commands...",
            id="input-box",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Initialize state on application mount."""
        from agent.core.config import config

        # Enable text selection
        log = self.query_one("#chat-output", SelectionLog)
        log.can_focus = True

        # Session store
        self._store = SessionStore()

        # Token budget
        self._token_budget = TokenBudget(max_tokens=128_000)
        self._refresh_token_budget()

        # Provider setup
        from agent.core.ai import ai_service

        # Trigger lazy initialization so providers are loaded from secrets/env
        try:
            ai_service._ensure_initialized()
        except Exception as e:
            self._write_system(
                f"[yellow]⚠ AI service init: {e}[/yellow]"
            )

        if self._initial_provider:
            try:
                ai_service.set_provider(self._initial_provider)
            except Exception as e:
                from rich.markup import escape
                self._write_system(f"[red]Error setting provider: {escape(str(e))}[/red]")

        # Apply --model override
        if self._initial_model and ai_service.provider:
            ai_service.models[ai_service.provider] = self._initial_model
            self._write_system(
                f"[dim]Model override: {self._initial_model}[/dim]"
            )

        # Validate that at least one AI provider is configured
        if not ai_service.provider:
            self._write_system(
                "[bold red]⚠ No AI provider configured.[/bold red]\n"
                "[yellow]Set one with:[/yellow]\n"
                "  • [bold]/provider gemini[/bold] — Google AI Studio\n"
                "  • [bold]/provider vertex[/bold] — Vertex AI (requires GOOGLE_CLOUD_PROJECT)\n"
                "  • [bold]/provider openai[/bold] — OpenAI (requires OPENAI_API_KEY)\n"
                "  • [bold]/provider anthropic[/bold] — Anthropic (requires ANTHROPIC_API_KEY)\n"
                "  • [bold]/provider ollama[/bold] — Local Ollama\n"
            )

        # Discover workflows and roles
        self._workflows = discover_workflows(config.agent_dir / "workflows")
        self._roles = discover_roles(config.etc_dir / "agents.yaml")

        # Populate sidebar lists
        wf_list = self.query_one("#workflow-list", ListView)
        for name, desc in sorted(self._workflows.items()):
            wf_list.append(ListItem(Label(f"/{name}"), name=name))

        role_list = self.query_one("#role-list", ListView)
        for name, desc in sorted(self._roles.items()):
            role_list.append(ListItem(Label(f"@{name}"), name=name))

        # Populate model list (only models whose provider is configured)
        model_list = self.query_one("#model-list", ListView)
        for display_name, provider, model_id in PREFERRED_MODELS:
            if provider in ai_service.clients:
                item = ListItem(
                    Label(f"{display_name}"),
                    name=f"{provider}:{model_id or ''}",
                )
                # Highlight the currently active model
                current_model = ai_service.models.get(ai_service.provider, "")
                if (
                    provider == ai_service.provider
                    and (model_id == current_model or model_id is None)
                ):
                    item.add_class("active-model")
                model_list.append(item)

        # Resume or create session
        session = self._store.get_latest_session()
        if session and session.messages:
            self._session = session
            self._replay_history()
        else:
            self._is_first_launch = True
            if session:
                # Reuse the empty session instead of creating another
                self._session = session
            else:
                self._new_session()

        # Welcome / first launch or empty session
        if self._is_first_launch:
            self._write_system(WELCOME_MESSAGE)

        # Update status bar
        self._update_status_bar()

        # Focus input
        self.query_one("#input-box", Input).focus()

        self._session_start_time = time.monotonic()
        logger.info("console.session.start", extra={"session_id": self._session.id})

    def _refresh_token_budget(self) -> None:
        """Recalculate and update the token budget for the current model."""
        if not self._token_budget:
            return
        new_max = self._get_model_context_window()
        if self._token_budget.max_tokens != new_max:
            self._token_budget.max_tokens = new_max
            self._update_status_bar()

    def _write_system(self, text: str) -> None:
        """Write a system message to the chat output."""
        log = self.query_one("#chat-output", SelectionLog)
        log.write(text)
        self._chat_text.append(text)

    def _write_user(self, text: str) -> None:
        """Write a user message to the chat output."""
        log = self.query_one("#chat-output", SelectionLog)
        log.write(f"\n[bold green]You:[/bold green] {text}")
        self._chat_text.append(f"You: {text}")

    def _write_assistant_start(self) -> None:
        """Initialize assistant response display."""
        log = self.query_one("#chat-output", SelectionLog)
        log.write("\nAssistant:", scroll_end=True)
        # Clear and prepare the streaming widget
        stream = self.query_one("#assistant-stream", Static)
        stream.update("")
        stream.display = True
        self._streaming_text = ""

    def _write_chunk(self, text: str) -> None:
        """Update the active streaming widget with new token."""
        self._streaming_text += text
        stream = self.query_one("#assistant-stream", Static)
        stream.update(self._streaming_text)

        # Throttle scroll_end to avoid flooding the event loop
        now = time.time()
        if not hasattr(self, "_last_scroll_time") or now - self._last_scroll_time > 0.1:
            log = self.query_one("#chat-output", SelectionLog)
            log.scroll_end(animate=False)
            self._last_scroll_time = now

    def _write_final_answer(self, text: str) -> None:
        """Render the complete AI response as a single block in the log."""
        from rich.markdown import Markdown
        # Hide the stream widget first
        stream = self.query_one("#assistant-stream", Static)
        stream.display = False
        stream.update("")
        
        log = self.query_one("#chat-output", SelectionLog)
        # Render the full response as Markdown to the persistent log
        log.write(Markdown(text), scroll_end=True)
        self._hide_exec_panel()

    def _hide_exec_panel(self) -> None:
        """Hide and clear the execution output panel."""
        try:
            exec_log = self.query_one("#exec-output", SelectionLog)
            exec_log.display = False
            exec_log.clear()
        except Exception:
            pass

    def _replay_history(self) -> None:
        """Replay conversation history into the chat output."""
        from rich.markdown import Markdown
        if not self._session:
            return
        for msg in self._session.messages:
            if msg.role == "user":
                self._write_user(msg.content)
            elif msg.role == "assistant":
                log = self.query_one("#chat-output", SelectionLog)
                log.write("\n[bold blue]Agent:[/bold blue] ")
                log.write(Markdown(msg.content))

    def _new_session(self) -> None:
        """Create a new conversation session."""
        provider_name = ""
        model_name = None
        try:
            from agent.core.ai import ai_service
            provider_name = ai_service.provider or ""
            model_name = ai_service.models.get(provider_name)
        except Exception:
            pass
        self._session = self._store.create_session(provider=provider_name, model=model_name)

    def _update_status_bar(self) -> None:
        """Update the bottom status bar with provider/model/tokens."""
        status = self.query_one("#status-bar", Static)
        provider = "none"
        model = "auto"
        try:
            from agent.core.ai import ai_service
            provider = ai_service.provider or "none"
            model_name = ai_service.models.get(provider, "auto")
            if self._session and self._session.model:
                model_name = self._session.model
            model = model_name or "auto"
        except Exception:
            pass

        tokens_used = 0
        tokens_max = self._token_budget.max_tokens if self._token_budget else 128000
        if self._session:
            from agent.core.tokens import token_manager
            for msg in self._session.messages:
                tokens_used += token_manager.count_tokens(
                    msg.content or "", provider=provider
                )

        session_title = ""
        if self._session and self._session.title:
            session_title = self._session.title
            if len(session_title) > 40:
                session_title = session_title[:37] + "…"

        if session_title:
            status.update(
                f" 💬 {session_title} │ {provider} │ {model} │ {tokens_used:,}/{tokens_max:,} tokens"
            )
        else:
            status.update(
                f" {provider} │ {model} │ {tokens_used:,}/{tokens_max:,} tokens"
            )

    # ─── Input Handling ───

    def on_key(self, event) -> None:
        """Handle key events for command history and search navigation."""
        input_box = self.query_one("#input-box", Input)
        input_focused = input_box.has_focus

        # ↑/↓ arrow: command history (only when input is focused)
        if input_focused and event.key == "up":
            if self._command_history:
                if self._history_index == -1:
                    self._history_stash = input_box.value
                    self._history_index = len(self._command_history) - 1
                elif self._history_index > 0:
                    self._history_index -= 1
                input_box.value = self._command_history[self._history_index]
                input_box.cursor_position = len(input_box.value)
            event.prevent_default()
            event.stop()
            return

        if input_focused and event.key == "down":
            if self._history_index != -1:
                if self._history_index < len(self._command_history) - 1:
                    self._history_index += 1
                    input_box.value = self._command_history[self._history_index]
                else:
                    self._history_index = -1
                    input_box.value = self._history_stash
                input_box.cursor_position = len(input_box.value)
            event.prevent_default()
            event.stop()
            return

        # n/r: search navigation (only when input is NOT focused)
        if not input_focused and self._search_matches:
            if event.key == "n":
                self._search_next()
                event.prevent_default()
                event.stop()
                return
            elif event.key == "r":
                self._search_prev()
                event.prevent_default()
                event.stop()
                return

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        raw = event.value.strip()
        if not raw:
            return

        # Add to command history
        if not self._command_history or self._command_history[-1] != raw:
            self._command_history.append(raw)
        self._history_index = -1
        self._history_stash = ""

        event.input.clear()

        from agent.core.config import config

        parsed = parse_input(
            raw,
            self._workflows,
            self._roles,
            workflows_dir=config.agent_dir / "workflows",
            agents_yaml=config.etc_dir / "agents.yaml",
        )

        if parsed.input_type == InputType.COMMAND:
            await self._handle_command(parsed)
        elif parsed.input_type == InputType.WORKFLOW:
            await self._handle_workflow(parsed)
        elif parsed.input_type == InputType.ROLE:
            await self._handle_role(parsed)
        else:
            await self._handle_chat(raw)

    async def _handle_command(self, parsed: ParsedInput) -> None:
        """Handle built-in /commands."""
        cmd = parsed.command

        if cmd == "help":
            help_text = format_help_text(self._workflows, self._roles)
            self._write_system(help_text)

        elif cmd == "quit":
            duration = time.monotonic() - getattr(self, "_session_start_time", time.monotonic())
            logger.info(
                "console.session.end",
                extra={
                    "session_id": self._session.id if self._session else "",
                    "duration_seconds": round(duration, 2),
                },
            )
            self.exit()

        elif cmd == "new":
            self._new_session()
            log = self.query_one("#chat-output", SelectionLog)
            log.clear()
            self._write_system("[dim]New conversation started.[/dim]")
            self._update_status_bar()

        elif cmd == "copy":
            self.action_copy()

        elif cmd == "conversations":
            sessions = self._store.list_sessions()
            if not sessions:
                self._write_system("[dim]No saved conversations.[/dim]")
                return

            # /history N  or  /conversations N  -> direct switch
            if parsed.args and parsed.args.strip().isdigit():
                idx = int(parsed.args.strip()) - 1
                if idx < 0 or idx >= len(sessions):
                    self._write_system("[red]Invalid conversation number.[/red]")
                    return
                target = self._store.get_session(sessions[idx].id)
                if not target:
                    self._write_system("[red]Conversation not found.[/red]")
                    return
                old_id = self._session.id if self._session else ""
                self._session = target
                log = self.query_one("#chat-output", SelectionLog)
                log.clear()
                self._replay_history()
                self._update_status_bar()
                logger.info(
                    "console.session.switch",
                    extra={"from_session": old_id, "to_session": target.id},
                )
                self._write_system(
                    f'[green]✓ Switched to: "{target.title}"[/green]'
                )
                return

            # No args -> list conversations
            lines = ["[bold]Saved Conversations:[/bold]\n"]
            for i, s in enumerate(sessions):
                msg_count = self._store._conn.execute(
                    "SELECT COUNT(*) FROM messages WHERE session_id = ?",
                    (s.id,),
                ).fetchone()[0]
                active = " [green]◀ active[/green]" if (
                    self._session and s.id == self._session.id
                ) else ""
                lines.append(
                    f"  [{i+1}] {s.title} "
                    f"[dim]({msg_count} msgs · {s.updated_at.strftime('%Y-%m-%d %H:%M')})[/dim]"
                    f"{active}"
                )
            lines.append("\n[dim]Switch: /history <number>  e.g. /history 2[/dim]")
            self._write_system("\n".join(lines))

        elif cmd == "switch":
            if not parsed.args or not parsed.args.strip().isdigit():
                self._write_system("[dim]Usage: /switch <number>[/dim]")
                return
            idx = int(parsed.args.strip()) - 1
            sessions = self._store.list_sessions()
            if idx < 0 or idx >= len(sessions):
                self._write_system("[red]Invalid conversation number.[/red]")
                return
            # Reload full session with messages (list_sessions skips them)
            target = self._store.get_session(sessions[idx].id)
            if not target:
                self._write_system("[red]Conversation not found.[/red]")
                return
            old_id = self._session.id if self._session else ""
            self._session = target
            
            # Sync ai_service with the selected session's settings
            from agent.core.ai import ai_service
            if target.provider:
                ai_service.set_provider(target.provider)
            if target.model:
                ai_service.models[ai_service.provider] = target.model

            log = self.query_one("#chat-output", SelectionLog)
            log.clear()
            self._replay_history()
            self._refresh_token_budget()
            self._update_status_bar()
            logger.info(
                "console.session.switch",
                extra={"from_session": old_id, "to_session": target.id},
            )
            self._write_system(
                f'[green]✓ Switched to: "{target.title}"[/green]'
            )

        elif cmd == "delete":
            if not self._session:
                return

            deleted_title = self._session.title

            def _on_delete_confirmed(confirmed: bool) -> None:
                if not confirmed:
                    return
                self._store.delete_session(self._session.id)
                log = self.query_one("#chat-output", SelectionLog)
                log.clear()
                self._write_system(
                    f'[dim]Deleted: "{deleted_title}"[/dim]'
                )
                # Switch to latest or create new
                latest = self._store.get_latest_session()
                if latest:
                    self._session = latest
                    self._replay_history()
                    self._write_system(
                        f'[green]✓ Now in: "{latest.title}"[/green]'
                    )
                else:
                    self._new_session()
                    self._write_system("[dim]New conversation started.[/dim]")
                self._update_status_bar()

            self.push_screen(
                ConfirmDeleteModal(title=self._session.title),
                _on_delete_confirmed,
            )

        elif cmd == "clear":
            log = self.query_one("#chat-output", SelectionLog)
            log.clear()
            self._chat_text.clear()

        elif cmd == "copy":
            self.action_copy_chat()

        elif cmd == "provider":
            from agent.core.ai import ai_service
            if parsed.args:
                query = parsed.args.strip()
                available = list(ai_service.clients.keys()) if hasattr(ai_service, 'clients') else []
                match = self._fuzzy_match(query, available)
                if match:
                    try:
                        ai_service.set_provider(match)
                        if self._session:
                            self._session.provider = match
                            # Clear old model to avoid cross-provider mismatch
                            self._session.model = None
                        self._write_system(
                            f"[green]✓ Provider switched to: {match}[/green]"
                        )
                    except Exception as e:
                        from rich.markup import escape as _esc
                        self._write_system(f"[red]Error: {_esc(str(e))}[/red]")
                else:
                    self._write_system(
                        f"[red]No match for '{query}'[/red]\n"
                        f"[dim]Available: {', '.join(available)}[/dim]"
                    )
            else:
                # No args — show picker
                available = list(ai_service.clients.keys()) if hasattr(ai_service, 'clients') else []
                current = ai_service.provider or ""
                if available:
                    items = [
                        (p, f"{'● ' if p == current else '  '}{p}")
                        for p in available
                    ]
                    def _on_provider_picked(chosen: str) -> None:
                        if chosen:
                            try:
                                ai_service.set_provider(chosen)
                                if self._session:
                                    self._session.provider = chosen
                                    # Clear old model to avoid cross-provider mismatch
                                    self._session.model = None
                                self._write_system(
                                    f"[green]✓ Provider switched to: {chosen}[/green]"
                                )
                                self._refresh_token_budget()
                            except Exception as e:
                                from rich.markup import escape as _esc
                                self._write_system(f"[red]Error: {_esc(str(e))}[/red]")
                            self._update_status_bar()
                    self.push_screen(
                        PickerModal("Select Provider", items),
                        _on_provider_picked,
                    )
                else:
                    self._write_system("[dim]No providers configured.[/dim]")
            self._update_status_bar()

        elif cmd == "model":
            if parsed.args:
                query = parsed.args.strip()
                # Fuzzy-match against available models
                try:
                    from agent.core.ai import ai_service
                    models = ai_service.get_available_models()
                    # Build list of display strings for fuzzy matching
                    model_keys = []
                    model_map = {}  # display_key -> model_id
                    for m in models:
                        mid = m.get("id", "")
                        mname = m.get("name", "")
                        key = f"{mid} {mname}".lower()
                        model_keys.append(key)
                        model_map[key] = mid
                    # Score by word overlap
                    query_words = query.lower().split()
                    scored = []
                    for key in model_keys:
                        score = sum(1 for w in query_words if w in key)
                        if score > 0:
                            scored.append((score, key))
                    scored.sort(key=lambda x: x[0], reverse=True)

                    if scored and scored[0][0] == len(query_words):
                        # All query words matched — pick the best
                        model_id = model_map[scored[0][1]]
                        if self._session:
                            self._session.model = model_id
                        # Persist to global service
                        ai_service.models[ai_service.provider] = model_id
                        self._write_system(
                            f"[green]✓ Model set to: {model_id}[/green]"
                        )
                    elif scored:
                        # Partial match — show top candidates
                        lines = [f"[yellow]Matches for '{query}':[/yellow]"]
                        for i, (s, key) in enumerate(scored[:8], 1):
                            mid = model_map[key]
                            lines.append(f"  {i}. {mid}")
                        lines.append("\n[dim]/model <full-id> to select[/dim]")
                        self._write_system("\n".join(lines))
                    else:
                        # No fuzzy match — set as exact string
                        if self._session:
                            self._session.model = query
                        self._write_system(
                            f"[green]✓ Model set to: {query}[/green]"
                        )
                    self._refresh_token_budget()
                except Exception:
                    # Fallback: set directly
                    if self._session:
                        self._session.model = query
                    self._write_system(
                        f"[green]✓ Model set to: {query}[/green]"
                    )
            else:
                # No args — show picker with available models
                try:
                    from agent.core.ai import ai_service
                    models = ai_service.get_available_models()
                    current = (self._session.model if self._session else None) or ""
                    if models:
                        items = [
                            (m["id"], f"{'● ' if m['id'] == current else '  '}{m['id']}  ({m.get('name', '')})")
                            for m in models[:30]  # cap to avoid UI overload
                        ]
                        def _on_model_picked(chosen: str) -> None:
                            if chosen:
                                if self._session:
                                    self._session.model = chosen
                                self._write_system(
                                    f"[green]✓ Model set to: {chosen}[/green]"
                                )
                                self._refresh_token_budget()
                                self._update_status_bar()
                        self.push_screen(
                            PickerModal("Select Model", items),
                            _on_model_picked,
                        )
                    else:
                        self._write_system("[dim]No models found for current provider.[/dim]")
                except Exception:
                    model = (self._session.model if self._session else None) or "auto (router)"
                    self._write_system(f"[bold]Current model:[/bold] {model}")
            self._update_status_bar()

        elif cmd == "rename":
            if parsed.args and self._session:
                self._store.rename_session(self._session.id, parsed.args.strip())
                self._session.title = parsed.args.strip()
                self._write_system(
                    f'[green]✓ Conversation renamed to: "{parsed.args.strip()}"[/green]'
                )

        elif cmd == "tools":
            # This is now less about provider support and more about what the
            # AgentExecutor is configured with. For now, we assume all tools
            # are available.
            from agent.core.adk.tools import TOOL_SCHEMAS
            lines = [
                "[bold]Agentic Tools:[/bold] [green]enabled[/green] via ReAct loop",
                "",
                "[bold]Available Tools:[/bold]",
            ]
            for schema in TOOL_SCHEMAS.values():
                 lines.append(
                    f"  [cyan]{schema['name']}[/cyan] — {schema['description'][:80]}"
                )
            self._write_system("\n".join(lines))

        elif cmd == "search":
            self._handle_search(parsed.args or "")


    async def _handle_workflow(self, parsed: ParsedInput) -> None:
        """Handle workflow invocation (e.g. /commit fix the tests)."""
        self._write_user(parsed.raw)

        # Lazy-load workflow content (deferred from parse_input to avoid
        # blocking file I/O on the UI thread).
        from agent.core.config import config as _cfg
        from agent.tui.commands import load_workflow_content

        wf_content = parsed.workflow_content or ""
        if not wf_content and parsed.workflow_name:
            wf_content = load_workflow_content(
                _cfg.agent_dir / "workflows", parsed.workflow_name
            ) or ""

        user_msg = parsed.args or f"Execute the {parsed.workflow_name} workflow."

        augmented_system = (
            f"{_get_system_prompt()}\n\n"
            f"The user is invoking the '{parsed.workflow_name}' workflow. "
            f"Here are the workflow instructions:\n\n{wf_content}"
        )

        self._store.add_message(self._session.id, "user", parsed.raw)
        if len(self._session.messages) == 0:
            self._store.auto_title(self._session.id, parsed.raw)
            self._session.title = parsed.raw[:60]

        self._session.messages.append(Message(role="user", content=parsed.raw))

        await self._stream_response(augmented_system, user_msg, use_tools=True)

    async def _handle_role(self, parsed: ParsedInput) -> None:
        """Handle role invocation (e.g. @security review the auth module)."""
        self._write_user(parsed.raw)

        # Lazy-load role context (deferred from parse_input to avoid
        # blocking file I/O on the UI thread).
        from agent.core.config import config as _cfg
        from agent.tui.commands import load_role_context

        role_context = parsed.role_context or ""
        if not role_context and parsed.role_name:
            role_context = load_role_context(
                _cfg.etc_dir / "agents.yaml", parsed.role_name
            ) or ""

        user_msg = parsed.args or f"Provide guidance as {parsed.role_name}."

        augmented_system = (
            f"{_get_system_prompt()}\n\n"
            f"The user is addressing you as the @{parsed.role_name} role. "
            f"Adopt this persona:\n\n{role_context}"
        )

        self._store.add_message(self._session.id, "user", parsed.raw)
        if len(self._session.messages) == 0:
            self._store.auto_title(self._session.id, parsed.raw)
            self._session.title = parsed.raw[:60]

        self._session.messages.append(Message(role="user", content=parsed.raw))

        await self._stream_response(augmented_system, user_msg, use_tools=True)

    async def _handle_chat(self, raw: str) -> None:
        """Handle a plain chat message."""
        self._write_user(raw)

        self._store.add_message(self._session.id, "user", raw)
        if len(self._session.messages) == 0:
            self._store.auto_title(self._session.id, raw)
            self._session.title = raw[:60]

        self._session.messages.append(Message(role="user", content=raw))

        await self._stream_response(_get_system_prompt(), raw)

    def _write_thought(self, thought: str) -> None:
        """Display agent's thought process."""
        log = self.query_one("#chat-output", SelectionLog)
        log.write(
            "\n[dim]🤔 Thinking...[/dim]",
            scroll_end=True,
        )

    def _write_tool_call(self, name: str, arguments: Dict[str, Any]) -> None:
        """Display a tool call notification in the exec panel."""
        from rich.markup import escape
        exec_log = self.query_one("#exec-output", SelectionLog)
        exec_log.display = True
        exec_log.clear()
        args_str = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
        exec_log.write(
            f"🔧 [bold]{escape(name)}[/bold]({escape(args_str)})",
            scroll_end=True,
        )

    def _write_tool_result(self, name: str, result: str) -> None:
        """Display a tool result summary in the exec panel."""
        from rich.markup import escape
        exec_log = self.query_one("#exec-output", SelectionLog)
        
        # Display the full result
        exec_log.write(
            f"[green]✓[/green] [dim]{escape(name)}[/dim]:\n{escape(result)}",
            scroll_end=True,
        )

    def _write_error(self, error_msg: str) -> None:
        """Display an error from the agent loop."""
        from rich.markup import escape
        log = self.query_one("#chat-output", SelectionLog)
        log.write(
            f"\n[bold red]AGENT ERROR:[/bold red] [red]{escape(error_msg)}[/red]",
            scroll_end=True,
        )

    def _write_tool_output(self, line: str) -> None:
        """Display a real-time line of tool output in the exec panel."""
        from rich.markup import escape
        
        def _update():
            exec_log = self.query_one("#exec-output", SelectionLog)
            exec_log.display = True
            exec_log.write(f"[dim]{escape(line)}[/dim]", scroll_end=True)
            
        self.call_from_thread(_update)

    # ── Search ──────────────────────────────────────────────────────

    def _handle_search(self, query: str) -> None:
        """Execute /search: find matches in the RichLog output."""
        if not query:
            self._write_system("[yellow]Usage: /search <query>[/yellow]")
            return

        self._search_query = query.lower()
        self._search_matches = []
        self._search_match_index = -1

        log = self.query_one("#chat-output", SelectionLog)
        # Walk the SelectionLog children looking for matches
        for child in log.children:
            text = getattr(child, "_search_text", "")
            if self._search_query in text.lower():
                self._search_matches.append(child)

        if not self._search_matches:
            self._write_system(
                f"[dim]No matches for '{query}'[/dim]"
            )
            self._update_status_bar()
            return

        # Jump to first match
        self._search_match_index = 0
        self._scroll_to_match()
        count = len(self._search_matches)
        self._write_system(
            f"[dim]Found {count} match{'es' if count != 1 else ''} "
            f"for '{query}'. Press n=next, r=reverse (unfocus input first).[/dim]"
        )

    def _search_next(self) -> None:
        """Jump to the next search match."""
        if not self._search_matches:
            return
        self._search_match_index = (
            (self._search_match_index + 1) % len(self._search_matches)
        )
        self._scroll_to_match()

    def _search_prev(self) -> None:
        """Jump to the previous search match."""
        if not self._search_matches:
            return
        self._search_match_index = (
            (self._search_match_index - 1) % len(self._search_matches)
        )
        self._scroll_to_match()

    def _scroll_to_match(self) -> None:
        """Scroll the SelectionLog to the current search match."""
        if self._search_match_index < 0:
            return
        child = self._search_matches[self._search_match_index]
        child.scroll_visible(animate=False)
        pos = self._search_match_index + 1
        total = len(self._search_matches)
        status = self.query_one("#status-bar", Static)
        status.update(
            f"Search: {pos}/{total} — "
            f"'{self._search_query}' │ n=next r=reverse │ Esc to dismiss"
        )


    async def _stream_response(
        self, system_prompt: str, user_prompt: str, *, use_tools: bool = False
    ) -> None:
        """Stream an AI response with disconnect recovery."""
        # Save for retry
        self._last_system_prompt = system_prompt
        self._last_user_prompt = user_prompt
        self._last_use_tools = use_tools
        self._partial_response = ""

        # Use an async worker to avoid blocking the UI
        self._do_stream(system_prompt, user_prompt, use_tools)

    @work
    async def _do_stream(
        self, system_prompt: str, user_prompt: str, use_tools: bool = False
    ) -> None:
        """Async worker that performs AI streaming with optional tool calling.

        Runs as an asyncio task via Textual's @work decorator. This allows
        for clean cancellation on app shutdown.
        """
        from agent.core.ai import ai_service
        from agent.core.config import config
        from agent.tui.agentic import supports_function_calling

        provider = ai_service.provider or "gemini"
        model = self._session.model if self._session else None

        self._write_assistant_start()

        if use_tools and supports_function_calling(provider):
            # --- Agentic path: AI can use tools (workflows/roles only) ---
            full_response = await self._do_agentic_stream(
                system_prompt, user_prompt, provider, model, config.repo_root
            )
        else:
            # --- Simple streaming path: text only (regular chat) ---
            full_response = await self._do_simple_stream(
                system_prompt, user_prompt, provider, model
            )

        # Always hide the exec panel when streaming is done
        try:
            self._hide_exec_panel()
        except Exception:
            pass

        if full_response is None:
            return  # Error was handled inside the method

        # Render the complete response as formatted Markdown
        if full_response:
            self._chat_text.append(f"Agent: {full_response}")
            self._write_final_answer(full_response)

        # Persist assistant response
        if full_response and self._session:
            self._store.add_message(self._session.id, "assistant", full_response)
            self._session.messages.append(Message(role="assistant", content=full_response))

        self._update_status_bar()

    async def _do_simple_stream(
        self, system_prompt: str, user_prompt: str, provider: str, model: str | None
    ) -> str | None:
        """Simple text streaming via ai_service.stream_complete."""
        from agent.core.ai import ai_service

        try:
            pruned_system, pruned_messages = self._token_budget.build_context(
                system_prompt, self._session.messages[:-1], provider=provider
            )
        except ValueError as e:
            logger.warning("Token budget overflow in simple stream: %s", e)
            pruned_system = system_prompt
            pruned_messages = []

        history_text = ""
        for msg in pruned_messages:
            role_label = "User" if msg.role == "user" else "Assistant"
            history_text += f"{role_label}: {msg.content}\n\n"
        history_text += f"User: {user_prompt}"

        full_response = ""
        try:
            # Run the synchronous generator in a thread but iterate it here
            def _gen():
                return ai_service.stream_complete(
                    pruned_system, history_text, model=model
                )

            # We use to_thread for the creation and then iterate safely
            # Since stream_complete is a generator, we iterate it in a loop
            # that we run in a thread to avoid blocking the main loop.
            def _iterate_sync():
                results = []
                for chunk in _gen():
                    results.append(chunk)
                    self.app.call_from_thread(self._write_chunk, chunk)
                return "".join(results)

            full_response = await asyncio.to_thread(_iterate_sync)
            
        except Exception as e:
            logger.error(
                "Streaming error: %s",
                str(e),
                extra={"error": str(e), "provider": provider},
                exc_info=True,
            )
            self._partial_response = full_response
            self._show_disconnect_modal(str(e))
            return None

        return full_response

    async def _do_agentic_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        provider: str,
        model: Optional[str],
        repo_root: Path,
    ) -> str | None:
        """Agentic loop with tool calling via AgentExecutor."""
        from agent.tui.agentic import run_agentic_loop
        try:
            pruned_system, pruned_messages = self._token_budget.build_context(
                system_prompt, self._session.messages[:-1], provider=provider
            )
        except ValueError as e:
            logger.warning("Token budget overflow in agentic stream: %s", e)
            pruned_system = system_prompt
            pruned_messages = []
        pruned_messages_dict = [
            {"role": m.role, "content": m.content} for m in pruned_messages
        ]

        full_response = ""
        try:
            full_response = await run_agentic_loop(
                system_prompt=pruned_system,
                user_prompt=user_prompt,
                messages=pruned_messages_dict,
                repo_root=repo_root,
                provider=provider,
                model=model,
                on_thought=self._write_thought,
                on_tool_call=self._write_tool_call,
                on_tool_result=self._write_tool_result,
                on_error=self._write_error,
                on_output=self._write_tool_output,
            )
        except Exception as e:
            logger.error(
                "Agentic loop error: %s",
                str(e),
                extra={"error": str(e), "provider": provider},
                exc_info=True,
            )
            self._partial_response = full_response
            self._show_disconnect_modal(str(e))
            return None

        return full_response


    def _show_disconnect_modal(self, error_msg: str) -> None:
        """Show the disconnect recovery modal."""

        async def handle_result(action: str) -> None:
            if action == "retry":
                self._write_system("\n[yellow]Retrying...[/yellow]")
                await self._stream_response(
                    self._last_system_prompt, self._last_user_prompt,
                    use_tools=getattr(self, '_last_use_tools', False)
                )
            elif action == "switch":
                from agent.core.ai import ai_service
                current = ai_service.provider or ""
                if ai_service.try_switch_provider(current):
                    new_provider = ai_service.provider
                    self._write_system(
                        f"\n[yellow]Switched to {new_provider}. Retrying...[/yellow]"
                    )
                    self._update_status_bar()
                    await self._stream_response(
                        self._last_system_prompt, self._last_user_prompt,
                        use_tools=getattr(self, '_last_use_tools', False)
                    )
                else:
                    self._write_system(
                        "\n[red]No alternative providers available.[/red]"
                    )
            else:
                if self._partial_response:
                    self._write_system(
                        "\n[dim](Partial response preserved)[/dim]"
                    )

        self.push_screen(DisconnectModal(error_msg=error_msg), handle_result)

    # ─── Sidebar Selection ───

    def _handle_model_selection(self, item_name: str) -> None:
        """Switch provider and model based on sidebar selection.

        Args:
            item_name: Encoded as 'provider:model_id'.
        """
        from agent.core.ai import ai_service

        parts = item_name.split(":", 1)
        provider = parts[0]
        model_id = parts[1] if len(parts) > 1 and parts[1] else None

        # Switch provider
        if provider in ai_service.clients:
            ai_service.provider = provider
            ai_service.is_forced = True
            if model_id:
                ai_service.models[provider] = model_id
            
            # Persist to session
            if self._session:
                self._session.provider = provider
                self._session.model = model_id

            # Update active-model highlighting
            model_list = self.query_one("#model-list", ListView)
            for child in model_list.children:
                if isinstance(child, ListItem):
                    child.remove_class("active-model")
                    if child.name == item_name:
                        child.add_class("active-model")

            # Find display name for confirmation
            display = model_id or provider
            for dname, prov, mid in PREFERRED_MODELS:
                if prov == provider and mid == model_id:
                    display = dname
                    break

            self._write_system(
                f"[bold cyan]🤖 Switched to {display} ({provider})[/bold cyan]"
            )

            # Refresh token budget for the new model
            self._refresh_token_budget()
        else:
            self._write_system(
                f"[red]Provider '{provider}' is not configured.[/red]"
            )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle workflow/role selection from sidebar."""
        input_box = self.query_one("#input-box", Input)
        item_name = event.item.name or ""

        # Determine if it's a workflow or role list
        parent = event.list_view
        if parent.id == "workflow-list":
            prefix = f"/{item_name} "
        elif parent.id == "role-list":
            prefix = f"@{item_name} "
        elif parent.id == "model-list":
            # Model selection: switch provider and model
            self._handle_model_selection(item_name)
            return
        else:
            return

        input_box.value = prefix
        input_box.focus()

        # Defer cursor positioning to AFTER focus auto-selects all text
        def _deselect() -> None:
            end = len(input_box.value)
            input_box.cursor_position = end
            # Clear selection by anchoring at the cursor position
            input_box.selection = (end, end)

        self.set_timer(0.1, _deselect)

    def action_dismiss_modal(self) -> None:
        """Dismiss the top modal screen on Escape."""
        if len(self.screen_stack) > 1:
            self.pop_screen()

    def action_copy(self) -> None:
        """Copy the entire chat history to the system clipboard."""
        import subprocess
        full_text = "\n".join(self._chat_text)
        try:
            process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
            process.communicate(full_text.encode('utf-8'))
            self.notify("Chat copied to clipboard", title="Copy Success")
        except Exception as e:
            self.notify(f"Could not copy: {e}", severity="error")

    def action_copy_or_quit(self) -> None:
        """Ctrl+C: Standard interrupt behavior (Quit)."""
        self.action_quit()

    @staticmethod
    def _fuzzy_match(query: str, candidates: list[str]) -> str | None:
        """Return the best fuzzy match for query among candidates."""
        q = query.lower()
        # Exact match first
        for c in candidates:
            if c.lower() == q:
                return c
        # Prefix match
        for c in candidates:
            if c.lower().startswith(q):
                return c
        # Substring match
        for c in candidates:
            if q in c.lower():
                return c
        # Word overlap
        words = q.split()
        scored = []
        for c in candidates:
            cl = c.lower()
            score = sum(1 for w in words if w in cl)
            if score > 0:
                scored.append((score, c))
        if scored:
            scored.sort(key=lambda x: x[0], reverse=True)
            return scored[0][1]
        return None

    def _get_model_context_window(self) -> int:
        """Look up the context window for the current model from router.yaml.

        Falls back to 128K which suits modern LLMs (Gemini 2.5 Pro: 2M,
        Flash: 1M, GPT-4o: 128K, Claude: 200K).
        """
        DEFAULT = 128_000
        try:
            from agent.core.config import config
            import yaml
            router_yaml = config.etc_dir / "router.yaml"
            if not router_yaml.exists():
                return DEFAULT
            data = yaml.safe_load(router_yaml.read_text()) or {}
            models = data.get("models", {})

            # Collect candidate model identifiers to match against
            candidates: list[str] = []

            # Session model (may have "models/" prefix, e.g. "models/gemini-pro-latest")
            session_model = (self._session.model if self._session else None) or ""
            if session_model:
                candidates.append(session_model)
                # Strip common prefixes like "models/"
                if "/" in session_model:
                    candidates.append(session_model.rsplit("/", 1)[-1])

            # Also try the ai_service's current model
            try:
                from agent.core.ai import ai_service
                provider = ai_service.provider or ""
                svc_model = ai_service.models.get(provider, "")
                if svc_model and svc_model not in candidates:
                    candidates.append(svc_model)
                    if "/" in svc_model:
                        candidates.append(svc_model.rsplit("/", 1)[-1])
            except Exception:
                provider = ""

            # Match candidates against router.yaml keys and deployment_ids
            for candidate in candidates:
                c_lower = candidate.lower()
                for _key, mdef in models.items():
                    deploy_id = mdef.get("deployment_id", "")
                    if (
                        _key.lower() == c_lower
                        or deploy_id.lower() == c_lower
                    ):
                        return int(mdef.get("context_window", DEFAULT))

            # Fallback: match by provider, pick the largest context window
            if provider:
                best = DEFAULT
                for _key, mdef in models.items():
                    if mdef.get("provider", "").lower() == provider.lower():
                        cw = int(mdef.get("context_window", DEFAULT))
                        if cw > best:
                            best = cw
                return best

            return DEFAULT
        except Exception:
            return DEFAULT

    def on_unmount(self) -> None:
        """Clean up on exit."""
        # Cancel all background workers (streaming threads) to prevent
        # the process from hanging after the TUI exits.
        self.workers.cancel_all()
        if self._store:
            self._store.close()
        if self._session:
            duration = time.monotonic() - getattr(self, "_session_start_time", time.monotonic())
            logger.info(
                "console.session.end",
                extra={
                    "session_id": self._session.id,
                    "duration_seconds": round(duration, 2),
                },
            )
