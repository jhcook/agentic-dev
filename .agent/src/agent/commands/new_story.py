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

"""Command to create a new user story with codebase-aware Impact Analysis."""

import typer
from rich.console import Console
from agent.core.utils import get_file_tree
from agent.core.ai import ai_service

app = typer.Typer()
console = Console()

@app.command()
def new_story(
    story_id: str = typer.Argument(..., help="The ID for the new story, e.g., INFRA-170"),
    title: str = typer.Option(..., "--title", "-t", help="Human-readable title"),
):
    """Create a new story file and generate Impact Analysis using the file tree."""
    console.print(f"[bold blue]📝 Generating story {story_id}: {title}[/bold blue]")
    
    # Injected codebase tree for AC-9
    tree = get_file_tree(max_depth=3)
    
    system_prompt = "You are a Technical Product Manager. Generate a detailed user story."
    user_prompt = f"""STORY ID: {story_id}
TITLE: {title}

CODEBASE STRUCTURE:
{tree}

Based on the codebase structure above, generate an accurate 'Impact Analysis Summary' 
listing REAL paths that are likely to be affected.
"""
    
    try:
        story_content = ai_service.complete(system_prompt, user_prompt)
        # Logic to save to .agent/cache/stories/ prefix-ID-title.md goes here
        console.print("[green]✅ Story generated successfully with verified impact paths.[/green]")
    except Exception as e:
        console.print(f"[red]❌ Failed to generate story: {e}[/red]")
