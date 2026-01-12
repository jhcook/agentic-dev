import typer
from rich.console import Console
from rich.markdown import Markdown
from typing import Optional

from agent.core.config import config
from agent.core.utils import find_story_file, load_governance_context, scrub_sensitive_data
from agent.core.ai import ai_service

app = typer.Typer()
console = Console()

def new_runbook(
    story_id: str = typer.Argument(..., help="The ID of the story to create a runbook for."),
):
    """
    Generate an implementation runbook using AI Governance Panel.
    """
    # 1. Find Story
    story_file = find_story_file(story_id)
    if not story_file:
         console.print(f"[bold red]❌ Story file not found for {story_id}[/bold red]")
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
    rules_content = scrub_sensitive_data(load_governance_context())
    

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

    system_prompt = f"""You are the AI Governance Panel for this repository.
Your role is to design and document a DETAILED Implementation Runbook for a software engineering task.

THE PANEL (You represent ALL these roles):
{panel_description}

INSTRUCTIONS:
1. You MUST adopt the perspective of EVERY role in the panel.
2. You MUST provide a distinct review section for EVERY role.
3. You MUST enforce the "Definition of Done".

INPUTS:
1. User Story (Requirements)
2. Governance Rules (Compliance constraints)

OUTPUT FORMAT:
Markdown file content ONLY.
The content MUST start with 'Status: PROPOSED'.

STRUCTURE:
# STORY-ID: <Title>

Status: PROPOSED

## Goal Description
<Clear summary of the objective>

## Panel Review Findings
(Critique the story/plan from each perspective)
{panel_checks if agents_path.exists() else '''
- **@Architect**: ...
- **@Security**: ...
- **@QA**: ...
- **@Docs**: ...
- **@Compliance**: ...
- **@Observability**: ...
'''}

## Implementation Steps
(Must be detailed enough for a qualified engineer)
### [Component Name]
#### [MODIFY | NEW | DELETE] [file path]
- <Specific instruction on what to change>
- <Code snippets if necessary for clarity>

## Verification Plan
### Automated Tests
- [ ] Test 1

### Manual Verification
- [ ] Step 1

## Definition of Done
### Documentation
- [ ] CHANGELOG.md updated
- [ ] README.md updated (if applicable)
- [ ] API Documentation updated (if applicable)

### Observability
- [ ] Logs are structured and free of PII
- [ ] Metrics added for new features

### Testing
- [ ] Unit tests passed
- [ ] Integration tests passed
"""

    user_prompt = f"""STORY CONTENT:
{story_content}

GOVERNANCE RULES:
{rules_content}
"""

    with console.status("[bold green]🤖 Panel is discussing...[/bold green]"):
        content = ai_service.complete(system_prompt, user_prompt)
        
    if not content:
        console.print("[bold red]❌ AI returned empty response.[/bold red]")
        raise typer.Exit(code=1)

    # 5. Write
    runbook_file.write_text(content)
    console.print(f"[bold green]✅ Runbook generated at: {runbook_file}[/bold green]")
    console.print("[yellow]⚠️  ACTION REQUIRED: Review and change 'Status: PROPOSED' to 'Status: ACCEPTED'.[/yellow]")
