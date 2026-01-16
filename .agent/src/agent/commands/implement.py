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

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax

from agent.core.ai import ai_service
from agent.core.config import config
from agent.core.utils import (
    find_runbook_file,
    load_governance_context,
    scrub_sensitive_data,
)

app = typer.Typer()
console = Console()

def parse_code_blocks(content: str) -> List[Dict[str, str]]:
    """
    Parse code blocks from AI-generated markdown content.
    
    Looks for patterns like:
    ```python:path/to/file.py
    code here
    ```
    
    Or simpler format:
    File: path/to/file.py
    ```python
    code here
    ```
    
    Returns:
        List of dicts with 'file' and 'content' keys
    """
    blocks = []
    
    # Pattern 1: ```language:filepath
    pattern1 = r'```[\w]+:([\w/\.\-_]+)\n(.*?)```'
    for match in re.finditer(pattern1, content, re.DOTALL):
        filepath = match.group(1).strip()
        code = match.group(2).strip()
        blocks.append({'file': filepath, 'content': code})
    
    # Pattern 2: File: filepath followed by code block
    pattern2 = r'(?:File|Modify|Create):\s*`?([^\n`]+)`?\s*\n```[\w]*\n(.*?)```'
    for match in re.finditer(pattern2, content, re.DOTALL | re.IGNORECASE):
        filepath = match.group(1).strip()
        code = match.group(2).strip()
        # Avoid duplicates
        if not any(b['file'] == filepath for b in blocks):
            blocks.append({'file': filepath, 'content': code})
    
    return blocks

def backup_file(file_path: Path) -> Optional[Path]:
    """Create a timestamped backup of a file before modification."""
    if not file_path.exists():
        return None
    
    backup_dir = Path(".agent/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{file_path.name}.backup-{timestamp}"
    backup_path = backup_dir / backup_name
    
    shutil.copy2(file_path, backup_path)
    return backup_path

def apply_change_to_file(filepath: str, content: str, yes: bool = False) -> bool:
    """
    Apply code changes to a file.
    
    Args:
        filepath: Path to the file to modify
        content: New content for the file
        yes: If True, skip confirmation
        
    Returns:
        True if changes were applied, False if skipped
    """
    file_path = Path(filepath)
    
    # Show diff preview
    console.print(f"\n[bold cyan]📝 Changes for: {filepath}[/bold cyan]")
    
    if file_path.exists():
        console.print("[yellow]File exists. Showing new content:[/yellow]")
    else:
        console.print("[green]New file will be created.[/green]")
    
    # Show code with syntax highlighting
    syntax = Syntax(content, "python" if filepath.endswith(".py") else "text", 
                   theme="monokai", line_numbers=True)
    console.print(syntax)
    
    # Confirmation
    if not yes:
        response = typer.confirm(f"\nApply changes to {filepath}?", default=False)
        if not response:
            console.print("[yellow]⏭️  Skipped[/yellow]")
            return False
    
    # Backup existing file
    if file_path.exists():
        backup_path = backup_file(file_path)
        if backup_path:
            console.print(f"[dim]💾 Backup created: {backup_path}[/dim]")
    
    # Create parent directories if needed
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write new content
    file_path.write_text(content)
    console.print(f"[bold green]✅ Applied changes to {filepath}[/bold green]")
    
    # Log the change
    log_file = Path(".agent/logs/implement_changes.log")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat()
    with open(log_file, "a") as f:
        f.write(f"[{timestamp}] Modified: {filepath}\n")
    
    return True

def implement(
    runbook_id: str = typer.Argument(..., help="The ID of the runbook to implement."),
    apply: bool = typer.Option(
        False, "--apply", help="Apply changes to files automatically."
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompts (use with --apply)."
    ),
    provider: Optional[str] = typer.Option(
        None, "--provider", help="Force AI provider (gh, gemini, openai)."
    ),
):
    """
    Execute an implementation runbook using AI.
    
    By default, generates implementation advice as markdown.
    With --apply, automatically applies code changes to files.
    With --yes, skips confirmation prompts (requires --apply).
    """
    # 0. Configure Provider Override if set
    if provider:
        ai_service.set_provider(provider)
    
    # Validate flag combination
    if yes and not apply:
        console.print("[bold red]❌ --yes requires --apply flag[/bold red]")
        raise typer.Exit(code=1)
    
    # 1. Find Runbook
    runbook_file = find_runbook_file(runbook_id)
    if not runbook_file:
         console.print(
             f"[bold red]❌ Runbook file not found for {runbook_id}[/bold red]"
         )
         raise typer.Exit(code=1)

    console.print(f"🛈 Implementing Runbook {runbook_id}...")
    runbook_content = scrub_sensitive_data(runbook_file.read_text())

    # 1.1 Enforce Runbook State
    if "Status: ACCEPTED" not in runbook_content:
        console.print(
            f"[bold red]❌ Runbook {runbook_id} is not ACCEPTED. "
            "Please review and update status to ACCEPTED "
            "before implementing.[/bold red]"
        )
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
         console.print(
             "[yellow]⚠️  Using GitHub CLI (limited context): "
             "Truncating guides and rules.[/yellow]"
         )
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
- Output code using this format:

File: path/to/file.py
```python
# Complete file content here
```

File: path/to/another.py
```python
# Complete file content here
```

- Provide complete, working code for each file.
- Include all necessary imports and logic.

OUTPUT FORMAT:
Return a Markdown response with file paths and code blocks as shown above.
"""

    user_prompt = f"""RUNBOOK CONTENT:
{runbook_content}

IMPLEMENTATION GUIDE:
{guide_content}

GOVERNANCE RULES:
{rules_content}
"""

    with console.status("[bold green]🤖 AI is coding...[/bold green]"):
        try:
            content = ai_service.complete(system_prompt, user_prompt)
        except Exception as e:
            console.print(f"[bold red]❌ AI Implementation failed: {e}[/bold red]")
            raise typer.Exit(code=1)
        
    if not content:
        console.print("[bold red]❌ AI returned empty response.[/bold red]")
        raise typer.Exit(code=1)

    # Only display the full AI response if not automatically applying
    if not apply:
        console.print(Markdown(content))
    
    # Apply changes if --apply flag is set
    if apply:
        console.print("\n[bold blue]🔧 Applying changes...[/bold blue]")
        
        code_blocks = parse_code_blocks(content)
        
        if not code_blocks:
            console.print(
                "[yellow]⚠️  No code blocks found in AI response. "
                "Nothing to apply.[/yellow]"
            )
            console.print(
                "[dim]Tip: Ensure the AI response includes code blocks "
                "with file paths.[/dim]"
            )
            return
        
        console.print(f"[dim]Found {len(code_blocks)} file(s) to modify[/dim]\n")
        
        applied_count = 0
        skipped_count = 0
        
        for block in code_blocks:
            filepath = block['file']
            code_content = block['content']
            
            if apply_change_to_file(filepath, code_content, yes):
                applied_count += 1
            else:
                skipped_count += 1
        
        # Summary
        console.print("\n[bold]Summary:[/bold]")
        console.print(f"  Applied: {applied_count}")
        console.print(f"  Skipped: {skipped_count}")
        
        if applied_count > 0:
            console.print("\n[bold green]✅ Changes applied successfully![/bold green]")
            console.print("[dim]💡 Backups saved to .agent/backups/[/dim]")
            console.print("[dim]📝 Change log: .agent/logs/implement_changes.log[/dim]")
    else:
        console.print("\n[bold green]✅ Implementation advice generated.[/bold green]")
        console.print("[dim]💡 Use --apply to automatically apply changes[/dim]")

