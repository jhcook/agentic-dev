import typer
from rich.console import Console
from rich.markdown import Markdown

from agent.core.config import config
from agent.core.utils import find_runbook_file, load_governance_context, scrub_sensitive_data
from agent.core.ai import ai_service

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

    # 2. Load Guide
    guide_path = config.agent_dir / "workflows/implement.md"
    guide_content = ""
    if guide_path.exists():
        guide_content = scrub_sensitive_data(guide_path.read_text())
    
    # 3. Load Rules
    rules_content = scrub_sensitive_data(load_governance_context())

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
