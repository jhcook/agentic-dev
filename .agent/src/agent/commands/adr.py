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
from rich.prompt import Prompt

from agent.core.config import config
from agent.core.utils import get_next_id, sanitize_title
from agent.db.client import upsert_artifact

console = Console()

def new_adr(
    adr_id: Optional[str] = typer.Argument(None, help="The ID of the ADR (e.g., ADR-001).")
):
    """
    Create a new Architectural Decision Record (ADR).
    """
    if not adr_id:
        # Auto-increment logic
        config.adrs_dir.mkdir(parents=True, exist_ok=True)
        adr_id = get_next_id(config.adrs_dir, "ADR")
        console.print(f"🛈 Auto-assigning ID: [bold cyan]{adr_id}[/bold cyan]")

    title = Prompt.ask("Enter ADR Title")
    safe_title = sanitize_title(title)
    filename = f"{adr_id}-{safe_title}.md"
    file_path = config.adrs_dir / filename
    
    if file_path.exists():
        console.print(f"[bold red]❌ ADR {adr_id} already exists at {file_path}[/bold red]")
        raise typer.Exit(code=1)
        
    template_path = config.templates_dir / "adr-template.md"
    
    if template_path.exists():
        content = template_path.read_text()
        content = f"# {adr_id}: {title}\n\n" + content
    else:
        content = f"""# {adr_id}: {title}

## Status
Proposed

## Context
Why this decision is needed.

## Decision
The architectural decision.

## Consequences
- Positive:
- Negative:
"""

    file_path.write_text(content)
    console.print(f"[bold green]✅ Created ADR: {file_path}[/bold green]")
    
    # Auto-sync
    if upsert_artifact(adr_id, "adr", content, author="agent"):
        console.print("[bold green]🔄 Synced to local cache[/bold green]")
    else:
        console.print("[yellow]⚠️  Failed to sync to local cache[/yellow]")

    # Auto-Sync to Providers (Priority Sync)
    from agent.sync.sync import push_safe
    console.print("[dim]Syncing to configured providers (Notion/Supabase)...[/dim]")
    push_safe(timeout=2, verbose=True)
