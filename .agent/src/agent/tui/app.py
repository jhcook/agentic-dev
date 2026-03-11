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
    RichLog,
    Static,
)
from textual.containers import VerticalScroll
from textual.widgets.option_list import Option

from agent.tui.chat import SelectionLog, ChatWorkerMixin, process_chat_stream, resolve_provider

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


from agent.tui.prompts import (
    WELCOME_MESSAGE,
    PREFERRED_MODELS,
    _get_system_prompt,
    build_chat_history,
)
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


class ConsoleApp(ChatWorkerMixin, App):
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

        # Agentic continuation state: when True, follow-up chat messages
        # continue through the agentic ReAct loop with tools enabled.
        self._agentic_mode: bool = False
        self._agentic_system_prompt: str = ""

        # Plain text buffer for copy-to-clipboard
        self._chat_text: list[str] = []
        self._streaming_text = ""

        # Security: Global tool approval for the current session
        self._tools_approved_for_session = False

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

        # Cache key widgets for robust access (fixes NoMatches query errors during modals)
        self._chat_log = self.query_one("#chat-output", SelectionLog)
        self._exec_log = self.query_one("#exec-output", SelectionLog)
        self._stream_widget = self.query_one("#assistant-stream", Static)
        self._status_bar = self.query_one("#status-bar", Static)
        self._input_box = self.query_one("#input-box", Input)

        # Enable text selection
        self._chat_log.can_focus = True
        self._exec_log.can_focus = True

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
        """Display system message."""
        self._chat_log.write(text)
        self._chat_text.append(text)

    def _write_user(self, text: str) -> None:
        """Display user's message."""
        from rich.markup import escape
        self._chat_log.write(f"\n[bold green]You:[/bold green] {escape(text)}")
        self._chat_text.append(f"You: {text}")

    def _write_assistant_start(self) -> None:
        """Initialize assistant response display."""
        self._chat_log.write("\nAssistant:", scroll_end=True)
        # Clear and prepare the streaming widget
        self._stream_widget.update("")
        self._stream_widget.display = True
        self._streaming_text = ""

    def _write_chunk(self, text: str) -> None:
        """Update the active streaming widget with new token."""
        self._streaming_text += text
        self._stream_widget.update(self._streaming_text)

        # Throttle scroll_end to avoid flooding the event loop
        now = time.time()
        if not hasattr(self, "_last_scroll_time") or now - self._last_scroll_time > 0.1:
            self._chat_log.scroll_end(animate=False)
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
        # Don't hide the exec panel here — keep it visible so users
        # can review agent thoughts, tool calls, and results.

    def _hide_exec_panel(self) -> None:
        """Hide the execution output panel (preserves content)."""
        try:
            exec_log = self.query_one("#exec-output", SelectionLog)
            exec_log.display = False
        except Exception:
            pass

    def _show_exec_panel(self) -> None:
        """Show the execution output panel for an agentic run.
        
        Clears previous content at the start of a new run so the panel
        shows only the current execution trace.
        """
        try:
            self._exec_log.clear()
            self._exec_log.display = True
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
        status = self._status_bar
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
            self._agentic_mode = False
            self._agentic_system_prompt = ""
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

        if parsed.workflow_name == "preflight":
            import subprocess
            try:
                staged = subprocess.check_output(["git", "diff", "--cached", "--name-only"]).strip()
                if not staged:
                    self._write_system("[red]Error: Cannot run /preflight without staged files. Please git add your changes first.[/red]")
                    return
            except Exception:
                pass

        augmented_system = (
            f"{_get_system_prompt()}\n\n"
            f"The user is invoking the '{parsed.workflow_name}' workflow. "
            f"Here are the workflow instructions:\n\n{wf_content}"
        )

        if parsed.workflow_name == "preflight":
            augmented_system += (
                "\n\n## Preflight Error Recovery\n"
                "If the `agent preflight` command reports a 'BLOCK' or fails, you MUST:\n"
                "1. Proactively use `run_command` or dedicated search tools to retrieve full failure details from logs/reports.\n"
                "2. Summarize the EXACT reasons for failure to the user.\n"
                "3. NEVER tell the user to 'check the UI' or 'review the output'. YOU must read the output and provide the analysis yourself."
            )

        self._store.add_message(self._session.id, "user", parsed.raw)
        if len(self._session.messages) == 0:
            self._store.auto_title(self._session.id, parsed.raw)
            self._session.title = parsed.raw[:60]

        self._session.messages.append(Message(role="user", content=parsed.raw))

        # Enable agentic continuation for follow-up messages
        self._agentic_mode = True
        self._agentic_system_prompt = augmented_system

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

        # Enable agentic continuation for follow-up messages
        self._agentic_mode = True
        self._agentic_system_prompt = augmented_system

        await self._stream_response(augmented_system, user_msg, use_tools=True)

    async def _handle_chat(self, raw: str) -> None:
        """Handle a plain chat message.

        If the conversation is in agentic mode (a workflow or role was
        recently invoked), this continues through the agentic ReAct loop
        with tools enabled so follow-up messages can execute tools.
        """
        self._write_user(raw)

        self._store.add_message(self._session.id, "user", raw)
        if len(self._session.messages) == 0:
            self._store.auto_title(self._session.id, raw)
            self._session.title = raw[:60]

        self._session.messages.append(Message(role="user", content=raw))

        if self._agentic_mode:
            # Continue through agentic loop with the workflow/role context
            await self._stream_response(
                self._agentic_system_prompt, raw, use_tools=True
            )
        else:
            # Plain chat — still enable tools so the agent can execute
            # commands, read files, etc. when the user asks questions
            # about repo state. Without this, the agent outputs raw
            # ReAct "Action:" text instead of actually calling tools.
            await self._stream_response(_get_system_prompt(), raw, use_tools=True)

    def _write_thought(self, thought: str, step: int) -> None:
        """Display agent's thought process in the execution panel."""
        import re
        from rich.markup import escape
        
        # Clean the thought of typical ReAct garbage
        cleaned = re.sub(r'```json.*?```', '', thought, flags=re.DOTALL|re.IGNORECASE)
        cleaned = re.sub(r'\{.*?\}', '', cleaned, flags=re.DOTALL)
        cleaned = cleaned.replace("Thought:", "").replace("Action:", "").replace("Action Input:", "").strip()
        
        if not cleaned:
            cleaned = "Thinking..."
            
        prefix = f"[bold blue]Step {step}[/bold blue]" if step > 1 else "[bold blue]Step 1[/bold blue]"
        
        self._exec_log.display = True
        self._exec_log.write(
            f"{prefix} 🤔 [dim]{escape(cleaned)}[/dim]",
            scroll_end=True,
        )

    def _write_tool_call(self, name: str, arguments: Dict[str, Any], step: int) -> None:
        """Display a tool call notification in the exec panel."""
        from rich.markup import escape
        self._exec_log.display = True
        # Separator between tool calls for readability (don't clear previous output)
        if self._exec_log.children:
            self._exec_log.write("─" * 40, scroll_end=True)
        args_str = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
        self._exec_log.write(
            f"[bold blue]Step {step}[/bold blue] 🔧 [bold]{escape(name)}[/bold]({escape(args_str)})",
            scroll_end=True,
        )

    def _write_tool_result(self, name: str, result: str, step: int) -> None:
        """Display a tool result summary in the exec panel."""
        from rich.markup import escape
        
        # Display the full result
        self._exec_log.write(
            f"[green]✓[/green] [dim]{escape(name)} (Step {step})[/dim]:\n{escape(result)}",
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
            self._exec_log.display = True
            self._exec_log.write(f"[dim]{escape(line)}[/dim]", scroll_end=True)

        try:
            self.call_from_thread(_update)
        except RuntimeError:
            # Already on the main thread (not in a worker thread)
            _update()

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

    def action_quit(self) -> None:
        """Force clean exit without waiting for blocking threads."""
        import os
        import sys
        import threading
        import time

        # Run unmount logic (saves state, closes DB) manually just in case
        try:
            self.on_unmount()
        except Exception:
            pass

        # Tell textual to exit gracefully if possible
        self.exit()

        # If textual hangs waiting for the executor, force kill it after 500ms.
        # We must restore the terminal first — os._exit bypasses Textual's
        # cleanup, which leaves the terminal in alt-screen mode and spews
        # raw ANSI escape codes into the parent shell.
        def _hard_exit():
            time.sleep(0.5)
            # Restore terminal state before hard exit
            try:
                fd = sys.stdout.fileno()
                if os.isatty(fd):
                    # Exit alternate screen buffer, show cursor, reset attributes
                    sys.stdout.write("\033[?1049l\033[?25h\033[0m")
                    sys.stdout.flush()
                    # Restore terminal to sane mode via stty
                    os.system("stty sane 2>/dev/null")
            except Exception:
                pass
            logging.shutdown()
            os._exit(0)
            
        threading.Thread(target=_hard_exit, daemon=True).start()

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
# nolint: loc-ceiling
