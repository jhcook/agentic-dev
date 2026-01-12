import typer
from rich.console import Console
from rich.prompt import Prompt
from typing import Optional

from agent.core.config import config
from agent.core.utils import get_next_id, sanitize_title

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
