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

import subprocess

def find_file_in_repo(filename: str) -> List[str]:
    """
    Search for a file in the git repo (respecting .gitignore).
    Returns list of matching relative paths.
    """
    try:
        # Search for the filename anywhere in the tracked files
        result = subprocess.check_output(
            ["git", "ls-files", "*"+filename], 
            stderr=subprocess.DEVNULL
        ).decode().strip()
        if not result:
            return []
        return result.split('\n')
    except Exception:
        return []

def find_directories_in_repo(dirname: str) -> List[str]:
    """
    Search for directories with a specific name in the repo.
    Excludes hidden directories (starting with .).
    """
    try:
        # standard 'find' command to look for directories with exact name
        # -type d : directories
        # -name : match name
        # -not -path '*/.*' : ignore hidden paths like .git/foo
        cmd = ["find", ".", "-type", "d", "-name", dirname, "-not", "-path", "*/.*"]
        result = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
        if not result:
            return []
        
        # clean up paths (./foo -> foo)
        paths = [p.lstrip("./") for p in result.split('\n') if p]
        return paths
    except Exception:
        return []

def resolve_path(filepath: str) -> Optional[Path]:
    """
    Resolve a potentially hallucinated file path to a real location.
    Returns None if the path is invalid/ambiguous and should be rejected.
    Returns Path object if resolved.
    """
    file_path = Path(filepath)
    
    # 1. Exact Match (Best Case)
    if file_path.exists():
        return file_path
        
    # 2. Existing File Search (renames/moves)
    # If the file exists somewhere else with the exact same name, assume that's it.
    candidates = find_file_in_repo(file_path.name)
    exact_matches = [c for c in candidates if Path(c).name == file_path.name]
    
    if len(exact_matches) == 1:
        # Single exact file match - Auto-Redirect
        new_path = exact_matches[0]
        if new_path != filepath:
            console.print(f"[yellow]⚠️  Path Auto-Correct (File Match): '{filepath}' -> '{new_path}'[/yellow]")
            return Path(new_path)
    elif len(exact_matches) > 1:
        # Ambiguous file match
        console.print(f"[bold red]❌ Ambiguous file path '{filepath}'. Found multiple existing files:[/bold red]")
        for i, c in enumerate(exact_matches):
            console.print(f"  {i+1}: {c}")
        console.print("[red]Aborting to prevent editing the wrong file.[/red]")
        return None

    # 3. Smart Directory Resolution (New File)
    # The file is new. Check if the directory path is valid.
    # We walk the path parts. If we hit a non-existent directory, we try to resolve it.
    parts = file_path.parts
    current_check = Path(".")
    
    for i, part in enumerate(parts[:-1]): # Skip filename
        next_check = current_check / part
        if not next_check.exists():
            # This directory component is missing. 
            # Example: 'src/foo.py' -> 'src' missing.
            # Search for a directory named 'part' in the repo.
            console.print(f"[dim]Directory '{next_check}' not found. Searching for '{part}'...[/dim]")
            dir_candidates = find_directories_in_repo(str(part))
            
            if len(dir_candidates) == 0:
                console.print(f"[bold red]❌ Cannot create new root hierarchy '{next_check}'.[/bold red]")
                console.print(f"[red]Directory '{part}' not found in repo.[/red]")
                return None
            elif len(dir_candidates) == 1:
                # Unique match found! Resolve the prefix.
                found_dir = dir_candidates[0]
                # Reconstruct path: found_dir + rest_of_path
                # existing parts: parts[:i] was valid (or root).
                # part is replaced by found_dir.
                # remaining is parts[i+1:]
                
                # Wait, if we are at 'src' (root), parts[:i] is empty.
                # found_dir is e.g. 'packages/app/src'
                # remaining is 'foo.py'
                
                rest_of_path = Path(*parts[i+1:])
                new_full_path = Path(found_dir) / rest_of_path
                console.print(f"[yellow]⚠️  Path Auto-Correct (Dir Match): '{filepath}' -> '{new_full_path}'[/yellow]")
                return new_full_path
            else:
                # Ambiguous directory
                console.print(f"[bold red]❌ Ambiguous directory '{part}'. Found multiple matches:[/bold red]")
                for i, c in enumerate(dir_candidates[:10]):
                    console.print(f"  - {c}")
                console.print("[red]Aborting. Please specify the full path.[/red]")
                return None
                
        current_check = next_check

    # If we made it here, the parent directories exist, or we are creating a file in root (allowed if not caught above).
    # But wait, logic above catches the *first* missing component.
    # If I create 'new_root/foo.py', 'new_root' is missing.
    # 'find_directories_in_repo' for 'new_root' -> returns [].
    # Returns None. So we BLOCK creating new root dirs implicitly. This is Desired.
    
    return file_path

def apply_change_to_file(filepath: str, content: str, yes: bool = False) -> bool:
    """
    Apply code changes to a file with smart path resolution.
    """
    resolved_path = resolve_path(filepath)
    if not resolved_path:
        return False
        
    file_path = resolved_path
    filepath = str(resolved_path)

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
    
    try:
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
    except Exception as e:
        console.print(f"[bold red]❌ Failed to write file: {e}[/bold red]")
        return False

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
    model: Optional[str] = typer.Option(
        None, "--model", help="Force specific AI model deployment ID."
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
    # Check for formats: "Status: ACCEPTED", "## Status\nACCEPTED", "## State\nACCEPTED"
    status_pattern = r"(?:^Status:\s*ACCEPTED|^## Status\s*\n+ACCEPTED|^## State\s*\n+ACCEPTED)"
    if not re.search(status_pattern, runbook_content_scrubbed, re.MULTILINE):
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

    # 4. Hybrid Strategy: Try Full Context -> Fallback to Chunking
    
    # Attempt 1: Full Context
    console.print("[dim]Attempting full context execution...[/dim]")
    
    full_content = ""
    fallback_needed = False
    


    try:
        system_prompt = """You are an Implementation Agent.
Your goal is to EXECUTE the tasks defined in the provided RUNBOOK.

CONTEXT:
1. RUNBOOK (The plan you must follow)
2. IMPLEMENTATION GUIDE (The process you must follow)
3. RULES (Governance you must obey)

INSTRUCTIONS:
- Review the Runbook's 'Proposed Changes'.
- Generate the actual code changes required.
- **IMPORTANT**: Use REPO-RELATIVE paths for all files (e.g., .agent/src/agent/main.py). 
- **WARNING**: DO NOT use 'agent/' as a root folder. The source code lives in '.agent/src/agent/'.
- Output code using this format:

File: path/to/file.py
```python
# Complete file content here
```

- Provide complete, working code for each file.
- Include all necessary imports.
"""
        user_prompt = f"""RUNBOOK CONTENT:
{runbook_content_scrubbed}

IMPLEMENTATION GUIDE:
{guide_content}

GOVERNANCE RULES:
{rules_content}
"""
        # Log context size
        context_size = len(system_prompt) + len(user_prompt)
        logging.info(f"AI Full Context Attempt | Context size: ~{context_size} chars")

        with console.status("[bold green]🤖 AI is coding (Full Context)...[/bold green]"):
             full_content = ai_service.complete(system_prompt, user_prompt, model=model)
             if not full_content:
                 raise Exception("Empty response from AI")

    except Exception as e:
        console.print(f"[yellow]⚠️ Full context failed: {e}[/yellow]")
        console.print("[bold blue]🔄 Falling back to Chunked Processing...[/bold blue]")
        fallback_needed = True

    # Attempt 2: Chunking (Fallback)
    if fallback_needed:
        # SEMANTIC FILTERING for Fallback Mode
        # We need to reduce context size to avoid transport crashes.
        # Instead of truncating, we filter out non-coding rules (process, roles, etc).
        console.print("[yellow]⚠️  Applying semantic context filtering (Coding Rules Only)...[/yellow]")
        
        # Load lean rules
        filtered_rules = scrub_sensitive_data(load_governance_context(coding_only=True))
        # Compress (remove comments/extra whitespace)
        filtered_rules = re.sub(r'<!--.*?-->', '', filtered_rules, flags=re.DOTALL)
        filtered_rules = re.sub(r'\n{3,}', '\n\n', filtered_rules)

        global_runbook_context, chunks = split_runbook_into_chunks(runbook_content_scrubbed)
        console.print(f"[dim]Runbook split into {len(chunks)} tasks[/dim]")

        # Reset provider state to ensure chunks use the preferred/forced provider,
        # ignoring any fallback switches that happened during Full Context failure.
        if provider:
             ai_service.set_provider(provider)
        else:
             ai_service.reset_provider()

        for idx, chunk in enumerate(chunks):
            if len(chunks) > 1:
                console.print(f"\n[bold blue]🚀 Processing Task {idx+1}/{len(chunks)}...[/bold blue]")

            system_prompt = """You are an Implementation Agent.
Your goal is to EXECUTE a SPECIFIC task from the provided RUNBOOK.
... (rest of chunking prompt) ...
"""
            # Reuse previous chunking logic here...
            # For brevity in this replacement, I need to make sure I don't lose the logic I wrote before.
            # I will use the previously written chunking loop here.
            
            chunk_system_prompt = """You are an Implementation Agent.
Your goal is to EXECUTE a SPECIFIC task from the provided RUNBOOK.
CONSTRAINTS:
1. ONLY implement the changes described in the 'CURRENT TASK'.
2. Maintain consistency with the 'GLOBAL RUNBOOK CONTEXT'.
3. Follow the 'IMPLEMENTATION GUIDE' and 'GOVERNANCE RULES'.
4. **IMPORTANT**: Use REPO-RELATIVE paths (e.g., .agent/src/agent/main.py). DO NOT use 'agent/' as root.
OUTPUT FORMAT:
Return a Markdown response with file paths and code blocks:

File: path/to/file.py
```python
# Complete file content here
```
"""
            chunk_user_prompt = f"""GLOBAL RUNBOOK CONTEXT (Truncated):
{global_runbook_context[:4000]}

--------------------------------------------------------------------------------
CURRENT TASK:
{chunk}
--------------------------------------------------------------------------------

RULES (Filtered):
{filtered_rules}
"""
            logging.info(f"AI Task {idx+1}/{len(chunks)} | Context size: ~{len(chunk_system_prompt) + len(chunk_user_prompt)} chars")



            chunk_result = None
            try:
                with console.status(f"[bold green]🤖 AI is coding task {idx+1}/{len(chunks)}...[/bold green]"):
                    chunk_result = ai_service.complete(chunk_system_prompt, chunk_user_prompt, model=model)
            except Exception as e:
                 console.print(f"[bold red]❌ Task {idx+1} failed during generation: {e}[/bold red]")
                 raise typer.Exit(code=1)

            if chunk_result:
                full_content += f"\n\n{chunk_result}"
                # Apply immediately if flag set (NOW SAFE: Outside spinner)
                if apply:
                    code_blocks = parse_code_blocks(chunk_result)
                    if code_blocks:
                        console.print(f"[dim]Found {len(code_blocks)} file(s) in this task[/dim]")
                        for block in code_blocks:
                            apply_change_to_file(block['file'], block['content'], yes)

    # Final Handling
    if not full_content:
         console.print("[bold red]❌ All attempts failed.[/bold red]")
         raise typer.Exit(code=1)

    # ... Display/Apply logic for full content ...
    if not apply and full_content:
         console.print(Markdown(full_content))
    elif apply and not fallback_needed: # If we did full context apply, do it now
         console.print("\n[bold blue]🔧 Applying changes...[/bold blue]")
         code_blocks = parse_code_blocks(full_content)
         # ... apply loop ...
         for block in code_blocks:
            apply_change_to_file(block['file'], block['content'], yes)

