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

import typer
from rich.console import Console
from rich.prompt import Prompt, IntPrompt
from typing import Optional

from agent.core.config import config
from agent.core.utils import get_next_id, sanitize_title
from agent.db.client import upsert_artifact

console = Console()

def new_plan(
    plan_id: Optional[str] = typer.Argument(None, help="The ID of the plan (e.g., INFRA-001).")
):
    """
    Create a new implementation plan manually from a template.
    """
    if not plan_id:
        console.print("Select Plan Category:")
        console.print("1. INFRA (Governance, CI/CD)")
        console.print("2. WEB (Frontend)")
        console.print("3. MOBILE (React Native)")
        console.print("4. BACKEND (FastAPI)")
        
        choice = IntPrompt.ask("Choice", choices=["1", "2", "3", "4"])
        
        prefixes = {1: "INFRA", 2: "WEB", 3: "MOBILE", 4: "BACKEND"}
        prefix = prefixes[choice]
        
        # Determine directory for auto-increment
        scope_dir = config.plans_dir / prefix
        scope_dir.mkdir(parents=True, exist_ok=True)
        
        plan_id = get_next_id(scope_dir, prefix)
        console.print(f"🛈 Auto-assigning ID: [bold cyan]{plan_id}[/bold cyan]")
    
    # Determine scope from ID
    scope = "MISC"
    if plan_id.startswith("INFRA-"):
        scope = "INFRA"
    elif plan_id.startswith("WEB-"):
        scope = "WEB"
    elif plan_id.startswith("MOBILE-"):
        scope = "MOBILE"
    elif plan_id.startswith("BACKEND-"):
        scope = "BACKEND"
    
    scope_dir = config.plans_dir / scope
    scope_dir.mkdir(parents=True, exist_ok=True)
    
    title = Prompt.ask("Enter Plan Title")
    safe_title = sanitize_title(title)
    filename = f"{plan_id}-{safe_title}.md"
    file_path = scope_dir / filename
    
    if file_path.exists():
        console.print(f"[bold red]❌ Plan {plan_id} already exists at {file_path}[/bold red]")
        raise typer.Exit(code=1)
        
    template_path = config.templates_dir / "plan-template.md"
    
    if template_path.exists():
        content = template_path.read_text()
        content = f"# {plan_id}: {title}\n\n" + content
    else:
        # Fallback template
        content = f"""# {plan_id}: {title}

## Related Story
STORY-XXX

## Summary
High-level description of the change.

## Objectives
- Objective 1
- Objective 2

## Verification
How we will confirm the plan was successful.
"""

    file_path.write_text(content)
    console.print(f"[bold green]✅ Created Plan: {file_path}[/bold green]")
    
    # Auto-sync
    if upsert_artifact(plan_id, "plan", content, author="agent"):
        console.print("[bold green]🔄 Synced to local cache[/bold green]")
    else:
        console.print("[yellow]⚠️  Failed to sync to local cache[/yellow]")


