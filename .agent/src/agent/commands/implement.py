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

import logging
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

def split_runbook_into_chunks(content: str) -> tuple[str, List[str]]:
    """
    Splits a runbook into global context and discrete implementation chunks.
    Returns (global_context, task_chunks)
    """
    headers = ["## Implementation Steps", "## Proposed Changes", "## Changes"]
    start_idx = -1
    for h in headers:
        if h in content:
            start_idx = content.find(h)
            break
    
    if start_idx == -1:
        return content, [content]

    global_context = content[:start_idx].strip()
    body = content[start_idx:]
    
    # Split the body into chunks by '### '
    raw_chunks = re.split(r'\n### ', body)
    
    chunks = []
    header_part = raw_chunks[0] # e.g. "## Implementation Steps\n..."
    
    for i in range(1, len(raw_chunks)):
        chunks.append(f"{header_part}\n### {raw_chunks[i]}")
        
    if not chunks:
        return global_context, [body]
        
    return global_context, chunks

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
    Execute an implementation runbook using AI with chunked task processing.
    
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
    original_runbook_content = runbook_file.read_text()
    runbook_content_scrubbed = scrub_sensitive_data(original_runbook_content)

    # 1.1 Enforce Runbook State
    if "Status: ACCEPTED" not in runbook_content_scrubbed:
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
    # COMPRESSION: Remove markdown comments and extra blank lines to save token space
    rules_content = re.sub(r'<!--.*?-->', '', rules_content, flags=re.DOTALL)
    rules_content = re.sub(r'\n{3,}', '\n\n', rules_content)

    # 4. Chunking Strategy
    global_runbook_context, chunks = split_runbook_into_chunks(runbook_content_scrubbed)
    
    if len(chunks) > 1:
        console.print(f"[bold blue]🛈 Strategy: Chunked Processing Active[/bold blue]")
        console.print(f"  • Runbook split into {len(chunks)} tasks to optimize reliability.")
        console.print(f"  • Full governance context is PRESERVED for each task.")
    else:
        console.print(f"[dim]Runbook small enough for single-pass processing.[/dim]")

    total_content = ""
    
    # 5. Iterative Implementation Loop
    for idx, chunk in enumerate(chunks):
        if len(chunks) > 1:
            console.print(f"\n[bold blue]🚀 Processing Task {idx+1}/{len(chunks)}...[/bold blue]")

        system_prompt = """You are an Implementation Agent.
Your goal is to EXECUTE a SPECIFIC task from the provided RUNBOOK.

CONSTRAINTS:
1. ONLY implement the changes described in the 'CURRENT TASK' section.
2. Maintain consistency with the 'GLOBAL RUNBOOK CONTEXT'.
3. Follow the 'IMPLEMENTATION GUIDE' and 'GOVERNANCE RULES'.

OUTPUT FORMAT:
Return a Markdown response with file paths and code blocks:

File: path/to/file.py
```python
# Complete file content here
```

- Provide complete, working code for each file mentioned in the task.
- Include all necessary imports.
"""

        user_prompt = f"""GLOBAL RUNBOOK CONTEXT:
{global_runbook_context}

--------------------------------------------------------------------------------
CURRENT TASK:
{chunk}
--------------------------------------------------------------------------------

IMPLEMENTATION GUIDE:
{guide_content}

GOVERNANCE RULES:
{rules_content}
"""

        # Log context size
        context_size = len(system_prompt) + len(user_prompt)
        logging.info(f"AI Task {idx+1}/{len(chunks)} | Context size: ~{context_size} chars")

        with console.status(f"[bold green]🤖 AI is coding task {idx+1}/{len(chunks)}...[/bold green]"):
            try:
                chunk_result = ai_service.complete(system_prompt, user_prompt)
                if not chunk_result:
                    logging.warning(f"Task {idx+1} returned empty content.")
                    continue
                total_content += f"\n\n{chunk_result}"
                
                # If applying automatically, apply this chunk immediately to keep momentum
                if apply:
                    code_blocks = parse_code_blocks(chunk_result)
                    if code_blocks:
                        console.print(f"[dim]Found {len(code_blocks)} file(s) in this task[/dim]")
                        for block in code_blocks:
                            apply_change_to_file(block['file'], block['content'], yes)
                    else:
                        console.print("[yellow]⚠️ No code blocks found in this task response.[/yellow]")
                
            except Exception as e:
                console.print(f"[bold red]❌ Task {idx+1} failed: {e}[/bold red]")
                if not apply: # If not applying, we can stop early
                    raise typer.Exit(code=1)
                # If applying, maybe continue? or stop? Given it's a chain, stopping is safer.
                raise typer.Exit(code=1)

    if not total_content:
        console.print("[bold red]❌ AI returned empty response for all tasks.[/bold red]")
        raise typer.Exit(code=1)

    # 6. Final Summary (only if not apply, as we already applied above)
    if not apply:
        console.print("\n[bold green]--- FINAL IMPLEMENTATION ADVICE ---[/bold green]")
        console.print(Markdown(total_content))
        console.print("\n[bold green]✅ Implementation advice generated in chunks.[/bold green]")
        console.print("[dim]💡 Use --apply to automatically apply changes sequentially.[/dim]")
    else:
        console.print("\n[bold green]✅ Sequential implementation complete![/bold green]")
        console.print("[dim]💡 Backups saved to .agent/backups/[/dim]")
        console.print("[dim]📝 Change log: .agent/logs/implement_changes.log[/dim]")

