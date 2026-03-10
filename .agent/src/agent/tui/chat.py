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

"""
Chat backend integration and selection context management.
"""

# Copyright 2026 Justin Cook

import logging
import asyncio
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, List, Optional
from textual.containers import VerticalScroll
from textual.widgets import Static
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, Static


from agent.core.logger import get_logger
from agent.core.utils import scrub_sensitive_data
from agent.core.ai.service import ai_service
from textual import work
from textual.screen import ModalScreen
from agent.tui.prompts import build_chat_history
from agent.tui.session import Message

logger = get_logger(__name__)

class SelectionLog(VerticalScroll):
    """A replacement for RichLog that holds Static widgets to allow for native text selection."""
    
    def __init__(self, *args, **kwargs):
        """Initialize the selection log with an empty history."""
        super().__init__(*args, **kwargs)
        self._history: List[Dict[str, str]] = []

    def write(self, renderable: Any, scroll_end: bool = False) -> None:
        """Write a new renderable to the selection log, optionally scrolling to the end."""
        widget = Static(renderable)
        widget._search_text = getattr(renderable, "markup", str(renderable))
        self.mount(widget)
        if scroll_end:
            self.scroll_end(animate=False)

    def add_selection(self, text: str, source: str):
        """Add a new selection to the log with scrubbing."""
        scrubbed = scrub_sensitive_data(text)
        self._history.append({"text": scrubbed, "source": source})
        logger.debug(f"Selection added from {source}", extra={"source": source})

    def clear(self) -> None:
        """Clear all contents from the selection log and reset history."""
        self.query("*").remove()
        self._history = []

    def get_context(self) -> str:
        """Formats the collected selections for LLM context."""
        return "\n---\n".join([item["text"] for item in self._history])

async def process_chat_stream(stream: AsyncGenerator[Dict[str, Any], None]) -> AsyncGenerator[str, None]:
    """
    Processes raw chunks from AI providers, handles error chunks,
    and yields clean text for the UI.
    """
    full_response = []
    try:
        async for chunk in stream:
            if "error" in chunk:
                error_msg = chunk["error"]
                logger.error(f"Stream error: {error_msg}", extra={"error": error_msg})
                yield f"\n[Error: {error_msg}]"
                return

            content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
            if content:
                yield content
                full_response.append(content)
    except Exception as e:
        logger.exception("Uncaught exception in chat stream processing")
        yield f"\n[Stream Interrupted: {str(e)}]"

def resolve_provider(provider_name: Optional[str] = None) -> Any:
    """Handoff logic to select the backend provider."""
    target = provider_name or "default"
    logger.info(f"Provider handoff initiated: {target}", extra={"provider": target})
    return ai_service.get_provider(target)

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


class ConfirmToolModal(ModalScreen[str]):
    """Modal to confirm tool execution (e.g., run_command)."""

    DEFAULT_CSS = """
    ConfirmToolModal {
        align: center middle;
    }
    #tool-confirm-dialog {
        width: 60;
        height: auto;
        border: thick $warning;
        background: $surface;
        padding: 1 2;
    }
    #tool-confirm-actions {
        layout: horizontal;
        align: center middle;
        height: 3;
    }
    #tool-confirm-actions Button {
        margin: 0 1;
    }
    """

    def __init__(self, tool_name: str, details: str) -> None:
        super().__init__()
        self._tool_name = tool_name
        self._details = details

    def compose(self) -> ComposeResult:
        with Container(id="tool-confirm-dialog"):
            yield Static(
                f"[bold yellow]⚠ Agent wants to execute {self._tool_name}[/bold yellow]\n\n"
                f"[cyan]{self._details}[/cyan]\n"
            )
            with Horizontal(id="tool-confirm-actions"):
                yield Button("Allow", variant="success", id="btn-tool-yes")
                yield Button("Allow Session", variant="warning", id="btn-tool-session")
                yield Button("Deny", variant="error", id="btn-tool-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-tool-yes":
            self.dismiss("yes")
        elif event.button.id == "btn-tool-session":
            self.dismiss("session")
        else:
            self.dismiss("no")


class ChatWorkerMixin:
    """
    Mixin for the main Textual App providing async stream processing
    and disconnect recovery capabilities decoupled from UI layout.
    """

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

        # Don't hide exec panel after agentic runs — keep it visible
        # so the user can review agent thoughts, tool calls, and results.
        # It will be cleared at the start of the NEXT agentic run.
        # Only hide for non-agentic (simple chat) streams.
        if not use_tools:
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

        history_text = build_chat_history(pruned_messages, user_prompt)

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
            error_str = str(e)
            # Auth errors are common (expired tokens) — log cleanly, not as a stack trace
            if "reauthentication" in error_str.lower() or "RefreshError" in type(e).__name__:
                logger.warning(
                    "Auth expired: %s. Run `gcloud auth application-default login` to fix.",
                    error_str,
                )
            else:
                logger.error(
                    "Streaming error: %s",
                    error_str,
                    extra={"error": error_str, "provider": provider},
                    exc_info=True,
                )
            self._partial_response = full_response
            self._show_disconnect_modal(error_str)
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

        # Initialize the exec panel at the start of the agentic run
        self._show_exec_panel()

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
                on_final_answer=lambda text: self._write_chunk(text),
                on_error=self._write_error,
                on_output=self._write_tool_output,
                on_tool_approval=self._ask_tool_approval,
            )
        except Exception as e:
            error_str = str(e)
            if "reauthentication" in error_str.lower() or "RefreshError" in type(e).__name__:
                logger.warning(
                    "Auth expired: %s. Run `gcloud auth application-default login` to fix.",
                    error_str,
                )
            else:
                logger.error(
                    "Agentic loop error: %s",
                    error_str,
                    extra={"error": error_str, "provider": provider},
                    exc_info=True,
                )
            self._partial_response = full_response
            self._show_disconnect_modal(error_str)
            return None

        return full_response

    async def _ask_tool_approval(self, tool_name: str, details: str) -> bool:
        """Present an async modal dialog to approve dangerous tools."""
        if self._tools_approved_for_session:
            return True
            
        result = await self.push_screen_wait(ConfirmToolModal(tool_name, details))
        
        if result == "session":
            self._tools_approved_for_session = True
            return True
        return result == "yes"

    async def push_screen_wait(self, screen: ModalScreen) -> Any:
        """Push a screen and wait for it to be dismissed, returning the result.
        
        Args:
            screen: The screen to push.
            
        Returns:
            The value passed to self.dismiss() in the modal.
        """
        future: asyncio.Future[Any] = asyncio.Future()
        
        def on_dismiss(result: Any) -> None:
            if not future.done():
                future.set_result(result)
                
        self.push_screen(screen, callback=on_dismiss)
        return await future


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

