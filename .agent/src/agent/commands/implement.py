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
from rich.markdown import Markdown

from agent.core.ai import ai_service
from agent.core.config import config
from agent.core.utils import (
    find_runbook_file,
    load_governance_context,
    scrub_sensitive_data,
)

app = typer.Typer()
console = Console()

def implement(
    runbook_id: str = typer.Argument(..., help="The ID of the runbook to implement."),
):
    """
    Execute an implementation runbook using AI.
    """
    # 1. Find Runbook
    runbook_file = find_runbook_file(runbook_id)
    if not runbook_file:
         console.print(f"[bold red]❌ Runbook file not found for {runbook_id}[/bold red]")
         raise typer.Exit(code=1)

    console.print(f"🛈 Implementing Runbook {runbook_id}...")
    runbook_content = scrub_sensitive_data(runbook_file.read_text())

    # 1.1 Enforce Runbook State
    if "Status: ACCEPTED" not in runbook_content:
        console.print(f"[bold red]❌ Runbook {runbook_id} is not ACCEPTED. Please review and update status to ACCEPTED before implementing.[/bold red]")
        raise typer.Exit(code=1)

    # 2. Load Guide
    guide_path = config.agent_dir / "workflows/implement.md"
    guide_content = ""
    if guide_path.exists():
        guide_content = scrub_sensitive_data(guide_path.read_text())
    
    # 3. Load Rules
    rules_content = scrub_sensitive_data(load_governance_context())

    # 3.1 Optimize Context for GitHub CLI
    if ai_service.provider == "gh":
         console.print("[yellow]⚠️  Using GitHub CLI (limited context): Truncating guides and rules.[/yellow]")
         guide_content = guide_content[:4000] # Cap guide at 4k chars
         rules_content = rules_content[:2000] # Cap rules at 2k chars

    # 4. Prompt
    system_prompt = """You are an Implementation Agent.
Your goal is to EXECUTE the tasks defined in the provided RUNBOOK.

CONTEXT:
1. RUNBOOK (The plan you must follow)
2. IMPLEMENTATION GUIDE (The process you must follow)
3. RULES (Governance you must obey)

INSTRUCTIONS:
- Review the Runbook's 'Proposed Changes'.
- Generate the actual code changes required.
- You should output the changes using a clear format that a user can follow or apply.
- Use 'diff' or 'code block' format for files.

OUTPUT FORMAT:
Return a Markdown response describing the actions taken and providing the code.
"""

    user_prompt = f"""RUNBOOK CONTENT:
{runbook_content}

IMPLEMENTATION GUIDE:
{guide_content}

GOVERNANCE RULES:
{rules_content}
"""

    with console.status("[bold green]🤖 AI is coding...[/bold green]"):
        content = ai_service.complete(system_prompt, user_prompt)
        
    if not content:
        console.print("[bold red]❌ AI returned empty response.[/bold red]")
        raise typer.Exit(code=1)

    console.print(Markdown(content))
    console.print("[bold green]✅ Implementation advice generated.[/bold green]")
