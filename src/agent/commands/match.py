import typer
from rich.console import Console
from agent.core.utils import load_governance_context, scrub_sensitive_data
from agent.core.config import config
from agent.core.ai import ai_service
import re
from pathlib import Path

app = typer.Typer()
console = Console()

def match_story(
    files: str = typer.Option(..., help="List of changed files (space or newline separated)"),
):
    """
    AI-assisted story selection based on context.
    """
    if not files:
        console.print("[red]❌ Error: --files argument is required.[/red]")
        raise typer.Exit(code=1)

    from agent.core.utils import find_best_matching_story
    
    result = find_best_matching_story(files)
    
    if not result:
        console.print("NONE")
        raise typer.Exit(code=1)
    
    console.print(result)
