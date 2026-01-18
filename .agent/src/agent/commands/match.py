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

from typing import Optional

import typer
from rich.console import Console

app = typer.Typer()
console = Console()

def match_story(
    files: str = typer.Option(..., help="List of changed files (space or newline separated)"),
    provider: Optional[str] = typer.Option(
        None, "--provider", help="Force AI provider (gh, gemini, openai)."
    ),
):
    """
    AI-assisted story selection based on context.
    """
    if not files:
        console.print("[red]❌ Error: --files argument is required.[/red]")
        raise typer.Exit(code=1)

    if provider:
        from agent.core.ai import ai_service
        ai_service.set_provider(provider)

    from agent.core.utils import find_best_matching_story
    
    result = find_best_matching_story(files)
    
    if not result:
        console.print("NONE")
        raise typer.Exit(code=1)
    
    console.print(result)
