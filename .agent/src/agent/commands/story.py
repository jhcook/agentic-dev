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
from rich.prompt import IntPrompt, Prompt

from agent.core.config import config
from agent.core.utils import get_next_id, sanitize_title
from agent.db.client import upsert_artifact

app = typer.Typer()
console = Console()

def new_story(
    story_id: Optional[str] = typer.Argument(None, help="The ID of the story (e.g., MOBILE-001).")
):
    """
    Create a new story file.
    """
    if not story_id:
        console.print("Select Story Category:")
        console.print("1. INFRA (Governance, CI/CD)")
        console.print("2. WEB (Frontend)")
        console.print("3. MOBILE (React Native)")
        console.print("4. BACKEND (FastAPI)")
        
        choice = IntPrompt.ask("Choice", choices=["1", "2", "3", "4"])
        
        prefixes = {1: "INFRA", 2: "WEB", 3: "MOBILE", 4: "BACKEND"}
        prefix = prefixes[choice]
        
        # Determine directory for auto-increment
        # Stories are in .agent/cache/stories/PREFIX
        scope_dir = config.stories_dir / prefix
        scope_dir.mkdir(parents=True, exist_ok=True)
        
        story_id = get_next_id(scope_dir, prefix)
        console.print(f"🛈 Auto-assigning ID: [bold cyan]{story_id}[/bold cyan]")
    
    # Determine scope from ID
    scope = "MISC"
    if story_id.startswith("INFRA-"):
        scope = "INFRA"
    elif story_id.startswith("WEB-"):
        scope = "WEB"
    elif story_id.startswith("MOBILE-"):
        scope = "MOBILE"
    elif story_id.startswith("BACKEND-"):
        scope = "BACKEND"
    
    scope_dir = config.stories_dir / scope
    scope_dir.mkdir(parents=True, exist_ok=True)
    
    title = Prompt.ask("Enter Story Title")
    safe_title = sanitize_title(title)
    filename = f"{story_id}-{safe_title}.md"
    file_path = scope_dir / filename
    
    if file_path.exists():
        console.print(f"[bold red]❌ Story {story_id} already exists at {file_path}[/bold red]")
        raise typer.Exit(code=1)
        
    template_path = config.templates_dir / "story-template.md"
    
    if template_path.exists():
        content = template_path.read_text()
        content = content.replace("STORY-XXX", story_id)
        content = content.replace(": Title", f": {title}")
    else:
        # Fallback template
        content = f"""# {story_id}: {title}

## State
DRAFT

## Problem Statement
What problem are we solving?

## User Story
As a <user>, I want <capability> so that <value>.

## Acceptance Criteria
- [ ] **Scenario 1**: Given <context>, When <action>, Then <result>.

## Non-Functional Requirements
- Performance
- Security

## Linked ADRs
- ADR-XXX

## Impact Analysis Summary
Components touched:
Workflows affected:
Risks identified:

## Test Strategy
How will we verify correctness?

## Rollback Plan
How do we revert safely?
"""

    file_path.write_text(content)
    console.print(f"[bold green]✅ Created story: {file_path}[/bold green]")
    
    # Auto-sync
    if upsert_artifact(story_id, "story", content, author="agent"):
        console.print("[bold green]🔄 Synced to local cache[/bold green]")
    else:
        console.print("[yellow]⚠️  Failed to sync to local cache[/yellow]")

    # Auto-Sync to Providers (Priority Sync)
    from agent.sync.sync import push_safe
    console.print(f"[dim]Syncing to configured providers (Notion/Supabase)...[/dim]")
    push_safe(timeout=2, verbose=True)

