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

import logging
import time
from pathlib import Path
from typing import Dict, Optional

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
    RichLog,
    Static,
)

from agent.tui.commands import (
    InputType,
    ParsedInput,
    discover_roles,
    discover_workflows,
    format_help_text,
    parse_input,
)
from agent.tui.session import ConversationSession, SessionStore, TokenBudget

logger = logging.getLogger(__name__)

# System prompt for the console agent
SYSTEM_PROMPT = (
    "You are an AI assistant integrated into the Agent CLI console. "
    "You help developers manage their codebase through the agentic development "
    "workflow. You have deep knowledge of the repository structure, available "
    "workflows, and governance model. Be concise and actionable."
)

WELCOME_MESSAGE = """\
[bold cyan]╭─── Agent Console ───╮[/bold cyan]

Welcome to the Agent Console! This is your conversation-driven
interface for managing the agent.

[dim]Key Shortcuts:[/dim]
  [bold]Tab[/bold]       Switch between panels
  [bold]↑ ↓[/bold]       Navigate lists
  [bold]Enter[/bold]     Select / Send message
  [bold]/help[/bold]     Show all commands

[dim]Conversations are stored locally in .agent/cache/console.db[/dim]
[dim]Messages are sent to the configured AI provider for processing.[/dim]
"""


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


class ConsoleApp(App):
    """The main Agent Console TUI application."""

    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("tab", "focus_next", "Next Panel", show=False),
        Binding("shift+tab", "focus_previous", "Previous Panel", show=False),
        Binding("escape", "dismiss_modal", "Dismiss", show=False),
    ]

    def __init__(
        self,
        provider: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._initial_provider = provider
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

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-area"):
            with Container(id="chat-container"):
                yield RichLog(id="chat-output", highlight=True, markup=True, wrap=True)
            with Vertical(id="sidebar"):
                with Container(id="workflow-panel"):
                    yield Static("Workflows")
                    yield ListView(id="workflow-list")
                with Container(id="role-panel"):
                    yield Static("Roles")
                    yield ListView(id="role-list")
        yield Static("", id="status-bar")
        yield Input(
            placeholder="Type a message or /help for commands...",
            id="input-box",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Initialize state on application mount."""
        from agent.core.config import config

        # Session store
        self._store = SessionStore()

        # Token budget from query.yaml
        max_tokens = 8192
        try:
            query_yaml = config.etc_dir / "query.yaml"
            if query_yaml.exists():
                data = config.load_yaml(query_yaml)
                max_tokens = int(data.get("max_context_tokens", 8192))
        except Exception:
            pass
        self._token_budget = TokenBudget(max_tokens=max_tokens)

        # Provider setup
        if self._initial_provider:
            try:
                from agent.core.ai import ai_service
                ai_service.set_provider(self._initial_provider)
            except Exception as e:
                self._write_system(f"[red]Error setting provider: {e}[/red]")

        # Validate that at least one AI provider is configured
        try:
            from agent.core.ai import ai_service
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
        except Exception:
            pass

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

        # Resume or create session
        session = self._store.get_latest_session()
        if session:
            self._session = session
            self._replay_history()
        else:
            self._is_first_launch = True
            self._new_session()

        # Welcome / first launch
        if self._is_first_launch:
            self._write_system(WELCOME_MESSAGE)

        # Update status bar
        self._update_status_bar()

        # Focus input
        self.query_one("#input-box", Input).focus()

        self._session_start_time = time.monotonic()
        logger.info("console.session.start", extra={"session_id": self._session.id})

    def _write_system(self, text: str) -> None:
        """Write a system message to the chat output."""
        log = self.query_one("#chat-output", RichLog)
        log.write(text)

    def _write_user(self, text: str) -> None:
        """Write a user message to the chat output."""
        log = self.query_one("#chat-output", RichLog)
        log.write(f"\n[bold green]You:[/bold green] {text}")

    def _write_assistant_start(self) -> None:
        """Write the assistant label before streaming."""
        log = self.query_one("#chat-output", RichLog)
        log.write("\n[bold blue]Agent:[/bold blue] ", shrink=False)

    def _write_chunk(self, chunk: str) -> None:
        """Append a streaming chunk to the chat output."""
        log = self.query_one("#chat-output", RichLog)
        log.write(chunk, shrink=False, scroll_end=True)

    def _replay_history(self) -> None:
        """Replay conversation history into the chat output."""
        if not self._session:
            return
        for msg in self._session.messages:
            if msg["role"] == "user":
                self._write_user(msg["content"])
            elif msg["role"] == "assistant":
                self._write_system(f"\n[bold blue]Agent:[/bold blue] {msg['content']}")

    def _new_session(self) -> None:
        """Create a new conversation session."""
        provider_name = ""
        try:
            from agent.core.ai import ai_service
            provider_name = ai_service.provider or ""
        except Exception:
            pass
        self._session = self._store.create_session(provider=provider_name)

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
        tokens_max = self._token_budget.max_tokens if self._token_budget else 8192
        if self._session:
            from agent.core.tokens import token_manager
            for msg in self._session.messages:
                tokens_used += token_manager.count_tokens(
                    msg.get("content", ""), provider=provider
                )

        status.update(
            f" {provider} │ {model} │ {tokens_used:,}/{tokens_max:,} tokens"
        )

    # ─── Input Handling ───

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        raw = event.value.strip()
        if not raw:
            return

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
            log = self.query_one("#chat-output", RichLog)
            log.clear()
            self._write_system("[dim]New conversation started.[/dim]")
            self._update_status_bar()

        elif cmd == "conversations":
            sessions = self._store.list_sessions()
            if not sessions:
                self._write_system("[dim]No saved conversations.[/dim]")
                return
            lines = ["[bold]Saved Conversations:[/bold]\n"]
            for i, s in enumerate(sessions):
                active = " [green]◀ active[/green]" if (
                    self._session and s.id == self._session.id
                ) else ""
                lines.append(
                    f"  [{i+1}] {s.title} "
                    f"[dim]({s.updated_at.strftime('%Y-%m-%d %H:%M')})[/dim]"
                    f"{active}"
                )
            lines.append("\n[dim]Type the number to switch, e.g. /switch 2[/dim]")
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
            target = sessions[idx]
            old_id = self._session.id if self._session else ""
            self._session = target
            log = self.query_one("#chat-output", RichLog)
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

        elif cmd == "delete":
            if not self._session:
                return
            result = await self.push_screen_wait(
                ConfirmDeleteModal(title=self._session.title)
            )
            if result:
                self._store.delete_session(self._session.id)
                self._write_system("[dim]Conversation deleted.[/dim]")
                # Switch to latest or create new
                latest = self._store.get_latest_session()
                if latest:
                    self._session = latest
                    log = self.query_one("#chat-output", RichLog)
                    log.clear()
                    self._replay_history()
                else:
                    self._new_session()
                    log = self.query_one("#chat-output", RichLog)
                    log.clear()
                    self._write_system("[dim]New conversation started.[/dim]")
                self._update_status_bar()

        elif cmd == "clear":
            log = self.query_one("#chat-output", RichLog)
            log.clear()

        elif cmd == "provider":
            from agent.core.ai import ai_service
            if parsed.args:
                try:
                    ai_service.set_provider(parsed.args.strip())
                    if self._session:
                        self._session.provider = parsed.args.strip()
                    self._write_system(
                        f"[green]✓ Provider switched to: {parsed.args.strip()}[/green]"
                    )
                except Exception as e:
                    self._write_system(f"[red]Error: {e}[/red]")
            else:
                current = ai_service.provider or "none"
                available = list(ai_service.clients.keys()) if hasattr(ai_service, 'clients') else []
                self._write_system(
                    f"[bold]Current provider:[/bold] {current}\n"
                    f"[bold]Available:[/bold] {', '.join(available) or 'none'}"
                )
            self._update_status_bar()

        elif cmd == "model":
            if parsed.args:
                if self._session:
                    self._session.model = parsed.args.strip()
                self._write_system(
                    f"[green]✓ Model set to: {parsed.args.strip()}[/green]"
                )
            else:
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
            f"{SYSTEM_PROMPT}\n\n"
            f"The user is invoking the '{parsed.workflow_name}' workflow. "
            f"Here are the workflow instructions:\n\n{wf_content}"
        )

        self._store.add_message(self._session.id, "user", parsed.raw)
        if len(self._session.messages) == 0:
            self._store.auto_title(self._session.id, parsed.raw)
            self._session.title = parsed.raw[:60]

        self._session.messages.append({"role": "user", "content": parsed.raw})

        await self._stream_response(augmented_system, user_msg)

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
            f"{SYSTEM_PROMPT}\n\n"
            f"The user is addressing you as the @{parsed.role_name} role. "
            f"Adopt this persona:\n\n{role_context}"
        )

        self._store.add_message(self._session.id, "user", parsed.raw)
        if len(self._session.messages) == 0:
            self._store.auto_title(self._session.id, parsed.raw)
            self._session.title = parsed.raw[:60]

        self._session.messages.append({"role": "user", "content": parsed.raw})

        await self._stream_response(augmented_system, user_msg)

    async def _handle_chat(self, raw: str) -> None:
        """Handle a plain chat message."""
        self._write_user(raw)

        self._store.add_message(self._session.id, "user", raw)
        if len(self._session.messages) == 0:
            self._store.auto_title(self._session.id, raw)
            self._session.title = raw[:60]

        self._session.messages.append({"role": "user", "content": raw})

        await self._stream_response(SYSTEM_PROMPT, raw)

    async def _stream_response(
        self, system_prompt: str, user_prompt: str
    ) -> None:
        """Stream an AI response with disconnect recovery."""
        # Save for retry
        self._last_system_prompt = system_prompt
        self._last_user_prompt = user_prompt
        self._partial_response = ""

        self._do_stream(system_prompt, user_prompt)

    @work(thread=True)
    def _do_stream(self, system_prompt: str, user_prompt: str) -> None:
        """Worker thread that performs the actual streaming call."""
        from agent.core.ai import ai_service

        # Build context with token budget
        provider = ai_service.provider or "gemini"
        pruned_system, pruned_messages = self._token_budget.build_context(
            system_prompt, self._session.messages[:-1], provider=provider
        )

        # Build a combined prompt from message history
        history_text = ""
        for msg in pruned_messages:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            history_text += f"{role_label}: {msg['content']}\n\n"
        history_text += f"User: {user_prompt}"

        model = self._session.model if self._session else None

        self.call_from_thread(self._write_assistant_start)

        full_response = ""
        try:
            for chunk in ai_service.stream_complete(
                pruned_system, history_text, model=model
            ):
                full_response += chunk
                self.call_from_thread(self._write_chunk, chunk)
        except Exception as e:
            logger.error(
                "Streaming error",
                extra={"error": str(e), "provider": provider},
            )
            self._partial_response = full_response

            # Show disconnect recovery modal
            self.call_from_thread(self._show_disconnect_modal, str(e))
            return

        # Persist assistant response
        if full_response and self._session:
            self._store.add_message(self._session.id, "assistant", full_response)
            self._session.messages.append(
                {"role": "assistant", "content": full_response}
            )

        self.call_from_thread(self._update_status_bar)

    def _show_disconnect_modal(self, error_msg: str) -> None:
        """Show the disconnect recovery modal."""

        async def handle_result(action: str) -> None:
            if action == "retry":
                self._write_system("\n[yellow]Retrying...[/yellow]")
                await self._stream_response(
                    self._last_system_prompt, self._last_user_prompt
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
                        self._last_system_prompt, self._last_user_prompt
                    )
                else:
                    self._write_system(
                        "\n[red]No alternative providers available.[/red]"
                    )
            else:
                if self._partial_response:
                    self._write_system(
                        f"\n[dim](Partial response preserved)[/dim]"
                    )

        self.push_screen(DisconnectModal(error_msg=error_msg), handle_result)

    # ─── Sidebar Selection ───

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
        else:
            return

        input_box.value = prefix
        input_box.focus()

        # Defer cursor positioning to AFTER focus auto-selects all text
        def _deselect() -> None:
            input_box.cursor_position = len(input_box.value)
            input_box.selection = (0, 0)  # Clear selection

        self.set_timer(0.05, _deselect)

    def action_dismiss_modal(self) -> None:
        """Dismiss the top modal screen on Escape."""
        if len(self.screen_stack) > 1:
            self.pop_screen()

    def on_unmount(self) -> None:
        """Clean up on exit."""
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
