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
import re
from rich.console import Console
from rich.table import Table
from typing import Optional, List, Dict, Any
from pathlib import Path

from agent.core.config import config
from agent.core.formatters import format_data
from agent.core.logger import get_logger
from agent.core.utils import scrub_sensitive_data

console = Console()
logger = get_logger("commands.list")

def get_file_state(file_path: Path) -> str:
    """
    Extracts the state from a markdown file.
    Looks for certain patterns like `## State\\n\\nACCEPTED`.
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

def write_output(content: str, output_file: str):
    """
    Write formatted output to a file.
    
    Args:
        content: The formatted content to write
        output_file: Path to output file
        
    Raises:
        typer.Exit: On write failure
    """
    try:
        output_path = Path(output_file)
        # Create parent directories if they don't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Write to file
        output_path.write_text(content)
        console.print(f"[green]✅ Output written to {output_file}[/green]")
        logger.info(f"Successfully wrote output to {output_file}")
    except PermissionError:
        error_msg = f"Permission denied: Cannot write to {output_file}"
        console.print(f"[red]❌ {error_msg}[/red]")
        logger.error(error_msg)
        raise typer.Exit(code=1)
    except Exception as e:
        error_msg = f"Failed to write to {output_file}: {e}"
        console.print(f"[red]❌ {error_msg}[/red]")
        logger.error(error_msg)
        raise typer.Exit(code=1)

def list_stories(
    state: Optional[str] = typer.Argument(None, help="Filter by state (e.g. DRAFT, COMMITTED)."),
    plan_id: Optional[str] = typer.Option(None, "--plan", help="Filter stories linked to this plan."),
    runbook_id: Optional[str] = typer.Option(None, "--runbook", help="Filter stories linked to this runbook."),
    output_format: str = typer.Option("pretty", "--format", "-f", help="Output format: pretty, json, csv, yaml, markdown, plain, tsv"),
    output_file: Optional[str] = typer.Option(None, "--output", "-o", help="Write output to file instead of stdout")
):
    """
    List all stories in .agent/cache/stories.
    """
    logger.info(f"Listing stories (format={output_format}, output={output_file})")
    stories_data: List[Dict[str, Any]] = []
    
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
        
        stories_data.append({
            "ID": scrub_sensitive_data(id_val),
            "Title": scrub_sensitive_data(title_val),
            "State": file_state,
            "Path": str(file_path.relative_to(config.repo_root))
        })

    # Handle output formatting
    if output_format == "pretty" and not output_file:
        # Use Rich table for pretty console output
        table = Table(title="📂 Stories")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Title", style="white")
        table.add_column("State", style="magenta")
        table.add_column("Path", style="dim")
        
        for story in stories_data:
            table.add_row(story["ID"], story["Title"], story["State"], story["Path"])
        
        if stories_data:
            console.print(table)
        else:
            console.print("  (No stories found matching criteria)")
    else:
        # Use formatter for other formats
        try:
            formatted_output = format_data(output_format, stories_data)
            
            if output_file:
                write_output(formatted_output, output_file)
            else:
                print(formatted_output)
        except ValueError as e:
            console.print(f"[red]❌ {e}[/red]")
            raise typer.Exit(code=1)

def list_plans(
    state: Optional[str] = typer.Argument(None, help="Filter by state."),
    output_format: str = typer.Option("pretty", "--format", "-f", help="Output format: pretty, json, csv, yaml, markdown, plain, tsv"),
    output_file: Optional[str] = typer.Option(None, "--output", "-o", help="Write output to file instead of stdout")
):
    """
    List all implementation plans in .agent/cache/plans.
    """
    logger.info(f"Listing plans (format={output_format}, output={output_file})")
    plans_data: List[Dict[str, Any]] = []
    
    for file_path in config.plans_dir.rglob("*.md"):
        file_state = get_file_state(file_path)
        if state and state.upper() != file_state.upper():
            continue
            
        id_val, title_val = get_title(file_path)
        
        plans_data.append({
            "ID": scrub_sensitive_data(id_val),
            "Title": scrub_sensitive_data(title_val),
            "State": file_state,
            "Path": str(file_path.relative_to(config.repo_root))
        })

    # Handle output formatting
    if output_format == "pretty" and not output_file:
        # Use Rich table for pretty console output
        table = Table(title="📂 Implementation Plans")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Title", style="white")
        table.add_column("State", style="magenta")
        table.add_column("Path", style="dim")
        
        for plan in plans_data:
            table.add_row(plan["ID"], plan["Title"], plan["State"], plan["Path"])
        
        if plans_data:
            console.print(table)
        else:
            console.print("  (No plans found)")
    else:
        # Use formatter for other formats
        try:
            formatted_output = format_data(output_format, plans_data)
            
            if output_file:
                write_output(formatted_output, output_file)
            else:
                print(formatted_output)
        except ValueError as e:
            console.print(f"[red]❌ {e}[/red]")
            raise typer.Exit(code=1)

def list_runbooks(
    state: Optional[str] = typer.Argument(None, help="Filter by state."),
    story_id: Optional[str] = typer.Option(None, "--story", help="Filter runbooks for this story."),
    output_format: str = typer.Option("pretty", "--format", "-f", help="Output format: pretty, json, csv, yaml, markdown, plain, tsv"),
    output_file: Optional[str] = typer.Option(None, "--output", "-o", help="Write output to file instead of stdout")
):
    """
    List all runbooks in .agent/cache/runbooks.
    """
    logger.info(f"Listing runbooks (format={output_format}, output={output_file})")
    runbooks_data: List[Dict[str, Any]] = []
    
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
        
        runbooks_data.append({
            "ID": scrub_sensitive_data(id_val),
            "Title": scrub_sensitive_data(title_val),
            "State": file_state,
            "Path": str(file_path.relative_to(config.repo_root))
        })

    # Handle output formatting
    if output_format == "pretty" and not output_file:
        # Use Rich table for pretty console output
        table = Table(title="📂 Runbooks")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Title", style="white")
        table.add_column("State", style="magenta")
        table.add_column("Path", style="dim")
        
        for runbook in runbooks_data:
            table.add_row(runbook["ID"], runbook["Title"], runbook["State"], runbook["Path"])
        
        if runbooks_data:
            console.print(table)
        else:
            console.print("  (No runbooks found)")
    else:
        # Use formatter for other formats
        try:
            formatted_output = format_data(output_format, runbooks_data)
            
            if output_file:
                write_output(formatted_output, output_file)
            else:
                print(formatted_output)
        except ValueError as e:
            console.print(f"[red]❌ {e}[/red]")
            raise typer.Exit(code=1)
