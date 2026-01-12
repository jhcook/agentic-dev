import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt, IntPrompt
from typing import Optional

from agent.core.config import config
from agent.core.utils import get_next_id, sanitize_title, find_story_file, load_governance_context, scrub_sensitive_data
from agent.core.ai import ai_service

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
    if plan_id.startswith("INFRA-"): scope = "INFRA"
    elif plan_id.startswith("WEB-"): scope = "WEB"
    elif plan_id.startswith("MOBILE-"): scope = "MOBILE"
    elif plan_id.startswith("BACKEND-"): scope = "BACKEND"
    
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

def plan(
    story_id: str = typer.Argument(..., help="The ID of the story to plan."),
):
    """
    Generate an implementation plan using AI.
    """
    # 1. Find Story
    story_file = find_story_file(story_id)
    if not story_file:
         console.print(f"[bold red]❌ Story file not found for {story_id}[/bold red]")
         raise typer.Exit(code=1)
         
    # 2. Check if Plan exists
    # Determine scope from subdirectory name of story
    scope = story_file.parent.name # e.g. INFRA
    plan_dir = config.plans_dir / scope
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plan_dir / f"{story_id}-impl-plan.md"
    
    if plan_file.exists():
        console.print(f"[yellow]⚠️  Plan already exists at {plan_file}[/yellow]")
        if not typer.confirm("Overwrite?"):
            raise typer.Exit(code=0)

    # 3. Gather Context
    console.print(f"🛈 Generating Plan for {story_id}...")
    story_content = scrub_sensitive_data(story_file.read_text())
    rules_content = scrub_sensitive_data(load_governance_context())
    
    # 4. Prompt AI
    system_prompt = """You are an Implementation Planning Agent.
Your goal is to create a detailed Step-by-Step Implementation Plan for a software engineering task.

INPUTS:
1. User Story (Requirements)
2. Governance Rules (Compliance constraints)

OUTPUT FORMAT:
Markdown file content ONLY. content must start with 'Status: PROPOSED'.

STRUCTURE:
# STROY-ID: <Title>

Status: PROPOSED

## Goal Description
<Short summary>

## Compliance Checklist
- [ ] @Security approved?
- [ ] @Architect approved?
- [ ] No PII leaks?

## Proposed Changes
### [Component]
- [NEW] path/to/file
- [MODIFY] path/to/file
  - Description of change...

## Verification Plan
### Automated Tests
- Command to run...

### Manual Verification
- Steps...
"""

    user_prompt = f"""STORY CONTENT:
{story_content}

GOVERNANCE RULES:
{rules_content}
"""

    with console.status("[bold green]🤖 AI is thinking...[/bold green]"):
        content = ai_service.complete(system_prompt, user_prompt)
        
    if not content:
        console.print("[bold red]❌ AI returned empty response.[/bold red]")
        raise typer.Exit(code=1)
        
    # 5. Write File
    plan_file.write_text(content)
    console.print(f"[bold green]✅ Plan generated at: {plan_file}[/bold green]")
