import typer
import re
from rich.console import Console
from rich.table import Table
from typing import Optional
from pathlib import Path

from agent.core.config import config

console = Console()

def get_file_state(file_path: Path) -> str:
    """
    Extracts the state from a markdown file.
    Looks for certain patterns like `## State\n\nACCEPTED`.
    """
    content = file_path.read_text(errors="ignore")
    
    # Try ## State pattern
    # Match "## State" followed by newline(s) and then some text
    match = re.search(r"^## State\s*\n+([A-Z]+)", content, re.MULTILINE)
    if match:
        return match.group(1).strip()
        
    # Try State: VALUE pattern
    match = re.search(r"^State:\s*([A-Za-z]+)", content, re.MULTILINE | re.IGNORECASE)
    if match:
        return match.group(1).strip().upper()
        
    return "UNKNOWN"

def get_title(file_path: Path) -> tuple[str, str]:
    """
    Extracts ID and Title from the first line header.
    Expected format: # ID: Title
    """
    try:
        with file_path.open('r') as f:
            first_line = f.readline().strip()
            
        match = re.match(r"^#\s*([^:]+):\s*(.*)$", first_line)
        if match:
            return match.group(1).strip(), match.group(2).strip()
            
        # Fallback to filename
        return file_path.stem, "(No title)"
    except Exception:
         return file_path.stem, "(Error reading file)"

def list_stories(
    state: Optional[str] = typer.Argument(None, help="Filter by state (e.g. DRAFT, COMMITTED)."),
    plan_id: Optional[str] = typer.Option(None, "--plan", help="Filter stories linked to this plan."),
    runbook_id: Optional[str] = typer.Option(None, "--runbook", help="Filter stories linked to this runbook.")
):
    """
    List all stories in .agent/cache/stories.
    """
    table = Table(title="📂 Stories")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="white")
    table.add_column("State", style="magenta")
    table.add_column("Path", style="dim")

    stories_found = False
    
    # Walk through stories dir
    for file_path in config.stories_dir.rglob("*.md"):
        content = file_path.read_text(errors="ignore")
        
        # Filters
        if plan_id and plan_id not in content:
            continue
        if runbook_id and runbook_id not in content:
            continue
            
        file_state = get_file_state(file_path)
        if state and state.upper() != file_state.upper():
            continue
            
        id_val, title_val = get_title(file_path)
        
        table.add_row(id_val, title_val, file_state, str(file_path.relative_to(config.repo_root)))
        stories_found = True

    if stories_found:
        console.print(table)
    else:
        console.print("  (No stories found matching criteria)")

def list_plans(
    state: Optional[str] = typer.Argument(None, help="Filter by state.")
):
    """
    List all implementation plans in .agent/cache/plans.
    """
    table = Table(title="📂 Implementation Plans")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="white")
    table.add_column("State", style="magenta")
    table.add_column("Path", style="dim")

    found = False
    
    for file_path in config.plans_dir.rglob("*.md"):
        file_state = get_file_state(file_path)
        if state and state.upper() != file_state.upper():
            continue
            
        id_val, title_val = get_title(file_path)
        
        table.add_row(id_val, title_val, file_state, str(file_path.relative_to(config.repo_root)))
        found = True

    if found:
        console.print(table)
    else:
        console.print("  (No plans found)")

def list_runbooks(
    state: Optional[str] = typer.Argument(None, help="Filter by state."),
    story_id: Optional[str] = typer.Option(None, "--story", help="Filter runbooks for this story.")
):
    """
    List all runbooks in .agent/cache/runbooks.
    """
    table = Table(title="📂 Runbooks")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="white") # Runbooks might not have standardized title, often just ID
    table.add_column("State", style="magenta")
    table.add_column("Path", style="dim")

    found = False
    
    for file_path in config.runbooks_dir.rglob("*.md"):
        file_stem = file_path.stem
        
        # Filter by story ID in filename usually? Or content?
        # Bash script: `if [[ "$base" != *"$filter_story"* ]]; then show=0; fi`
        if story_id and story_id not in file_stem:
            continue
            
        file_state = get_file_state(file_path)
        if state and state.upper() != file_state.upper():
            continue
        
        # Runbooks often don't have the same header format, but let's try
        id_val, title_val = get_title(file_path)
        
        table.add_row(id_val, title_val, file_state, str(file_path.relative_to(config.repo_root)))
        found = True

    if found:
        console.print(table)
    else:
        console.print("  (No runbooks found)")
