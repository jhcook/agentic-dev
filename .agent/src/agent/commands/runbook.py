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

from agent.core.ai import ai_service
from agent.core.config import config
from agent.core.utils import (
    find_story_file,
    load_governance_context,
    scrub_sensitive_data,
)
from agent.db.client import upsert_artifact

app = typer.Typer()
console = Console()

def new_runbook(
    story_id: str = typer.Argument(..., help="The ID of the story to create a runbook for."),
    provider: Optional[str] = typer.Option(
        None, "--provider", help="Force AI provider (gh, gemini, openai)."
    ),
):
    """
    Generate an implementation runbook using AI Governance Panel.
    """
    # 0. Configure Provider Override if set
    if provider:
        ai_service.set_provider(provider)
    
    # 1. Find Story
    story_file = find_story_file(story_id)
    if not story_file:
         console.print(f"[bold red]❌ Story file not found for {story_id}[/bold red]")
         raise typer.Exit(code=1)

    # 1.1 Enforce Story State
    import re
    story_text = story_file.read_text()
    
    # Check for both formats: "State: COMMITTED" (inline) and "## State\nCOMMITTED" (multiline)
    state_pattern = r"(?:^State:\s*COMMITTED|^## State\s*\n+COMMITTED|^Status:\s*COMMITTED)"
    if not re.search(state_pattern, story_text, re.MULTILINE):
        console.print(f"[bold red]❌ Story {story_id} is not COMMITTED. Please commit the story before creating a runbook.[/bold red]")
        raise typer.Exit(code=1)

    # 2. Check Paths
    scope = story_file.parent.name
    runbook_dir = config.runbooks_dir / scope
    runbook_dir.mkdir(parents=True, exist_ok=True)
    runbook_file = runbook_dir / f"{story_id}-runbook.md"
    
    if runbook_file.exists():
        console.print(f"[yellow]⚠️  Runbook already exists at {runbook_file}[/yellow]")
        if not typer.confirm("Overwrite?"):
            raise typer.Exit(code=0)

    # 3. Context
    console.print(f"🛈 invoking AI Governance Panel for {story_id}...")
    story_content = scrub_sensitive_data(story_file.read_text())
    rules_full = scrub_sensitive_data(load_governance_context())
    
    # Truncate rules to avoid token limits (GitHub CLI has 8000 token max)
    rules_content = rules_full[:3000] + "\n\n[...truncated for token limits...]" if len(rules_full) > 3000 else rules_full
    

    # 4. Prompt
    # Load agents dynamically
    import yaml
    agents_path = config.agent_dir / "agents.yaml"
    panel_description = ""
    panel_checks = ""
    
    if agents_path.exists():
        try:
            agents_data = yaml.safe_load(agents_path.read_text())
            for agent in agents_data.get("team", []):
                role = agent.get("role", "unknown")
                name = agent.get("name", role.capitalize())
                desc = agent.get("description", "")
                panel_description += f"- @{role.capitalize()} ({name}): {desc}\n"
                
                checks = "\n".join([f"  - {c}" for c in agent.get("governance_checks", [])])
                panel_checks += f"- **@{role.capitalize()}**:\n{checks}\n"
        except Exception as e:
             console.print(f"[yellow]⚠️  Failed to load agents.yaml: {e}. Using defaults.[/yellow]")
             panel_description = "- @Architect, @Security, @QA, @Docs, @Compliance, @Observability"
    else:
        panel_description = "- @Architect, @Security, @QA, @Docs, @Compliance, @Observability"

    # Load Template
    template_path = config.templates_dir / "runbook-template.md"
    if not template_path.exists():
        console.print(f"[bold red]❌ Runbook template not found at {template_path}[/bold red]")
        raise typer.Exit(code=1)
        
    template_content = template_path.read_text()
    
    # We want the LLM to fill in the template. 
    # We will provide the structure as a requirement.
    
    system_prompt = f"""You are the AI Governance Panel for this repository.
Your role is to design and document a DETAILED Implementation Runbook for a software engineering task.

THE PANEL (You represent ALL these roles):
{panel_description}

INSTRUCTIONS:
1. You MUST adopt the perspective of EVERY role in the panel.
2. You MUST provide a distinct review section for EVERY role.
3. You MUST enforce the "Definition of Done".
4. You MUST follow the structure of the provided TEMPLATE exactly.

INPUTS:
1. User Story (Requirements)
2. Governance Rules (Compliance constraints)

TEMPLATE STRUCTURE (Found in {template_path.name}):
{template_content}

Your output must be the FILLED IN template, starting with the Header. Do NOT wrap in markdown blocks.
Replace placeholders like <Title>, <Clear summary...>, etc. with actual content.
Update '## Panel Review Findings' with specific commentary.
Update '## Targeted Refactors & Cleanups (INFRA-043)' with any relevant cleanups found.
"""

    user_prompt = f"""STORY CONTENT:
{story_content}

GOVERNANCE RULES:
{rules_content}

Generate the runbook now.
"""

    with console.status("[bold green]🤖 Panel is discussing...[/bold green]"):
        content = ai_service.complete(system_prompt, user_prompt)
        
    if not content:
        console.print("[bold red]❌ AI returned empty response.[/bold red]")
        raise typer.Exit(code=1)

    # 5. Write
    runbook_file.write_text(content)
    console.print(f"[bold green]✅ Runbook generated at: {runbook_file}[/bold green]")
    
    # Auto-sync
    runbook_id = f"{story_id}" # Using Story ID for Runbook ID as well, with type='runbook'
    if upsert_artifact(runbook_id, "runbook", content, author="agent"):
         console.print("[bold green]🔄 Synced to local cache[/bold green]")
    else:
         console.print("[yellow]⚠️  Failed to sync to local cache[/yellow]")

    console.print("[yellow]⚠️  ACTION REQUIRED: Review and change to '## State\\nACCEPTED'.[/yellow]")
