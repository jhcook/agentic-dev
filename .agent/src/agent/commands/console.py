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

"""CLI entry point for the Agent Console TUI (INFRA-087).

ADR-028: This command MUST be synchronous (``def``, not ``async def``).
The Textual ``App.run()`` call blocks synchronously internally.
"""

from typing import Optional

import typer


def console(
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        help="Force AI provider (gh, gemini, vertex, openai, anthropic, ollama)",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        help="Override the default model for the selected provider",
    ),
) -> None:
    """Interactive terminal console with persistent conversations."""
    try:
        from agent.tui.app import ConsoleApp
    except ImportError:
        typer.echo(
            "Error: The 'textual' package is required for the console.\n"
            "Install it with: pip install 'agent[console]'"
        )
        raise typer.Exit(1)

    if provider:
        try:
            from agent.core.ai import ai_service
            ai_service.set_provider(provider)
        except Exception as e:
            typer.echo(f"Error setting provider: {e}")
            raise typer.Exit(1)

    import os
    try:
        app = ConsoleApp(provider=provider, model=model)
        app.run()
    finally:
        # Force-exit to terminate any lingering worker threads that may be
        # stuck in blocking I/O (e.g. waiting for an AI provider response).
        # We use os._exit(0) in finally to ensure a clean prompt return
        # even if a KeyboardInterrupt (Ctrl+C) occurred mid-shutdown.
        os._exit(0)
