import typer
import subprocess
import sys
import shutil
from pathlib import Path
from typing import List, Optional
from rich.console import Console

console = Console()

def get_changed_files(base: Optional[str] = None, staged_only: bool = True) -> List[str]:
    """
    Get a list of changed files using git.
    
    Args:
        base: The base branch to compare against (e.g., "main").
        staged_only: If True, only check staged files (default behavior).
    """
    cmd = ["git", "diff", "--name-only", "--diff-filter=d"]
    
    if base:
        # Compare against base branch
        # git diff --name-only base...HEAD
        cmd.extend([f"{base}...HEAD"])
    elif staged_only:
        # Check staged files
        # git diff --name-only --cached
        cmd.append("--cached")
    else:
        # Unstaged changes (not requested but useful context, maybe for future)
        # For now, if neither base nor staged defaults are used, we might default to all? 
        # But for 'get_changed_files', let's stick to git logic.
        pass

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
        # Filter for files that exist (git diff might show deleted files if filter=d didn't catch specific rename edge cases)
        return [f for f in files if Path(f).exists()]
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Error running git:[/bold red] {e}")
        return []

def run_ruff(files: List[str]) -> bool:
    """Run ruff on the specified files. Returns True if successful."""
    if not files:
        return True
    
    # Try running as module first (safer in venv)
    cmd = [sys.executable, "-m", "ruff", "check"] + files
    
    console.print(f"[bold blue]Running ruff on {len(files)} files...[/bold blue]")
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def run_shellcheck(files: List[str]) -> bool:
    """Run shellcheck on the specified files. Returns True if successful."""
    if not files:
        return True

    shellcheck_exec = shutil.which("shellcheck")
    if not shellcheck_exec:
        # Check if user on mac, suggest brew
        console.print("[bold yellow]Warning:[/bold yellow] 'shellcheck' not found. Skipping Shell linting.")
        return True

    console.print(f"[bold blue]Running shellcheck on {len(files)} files...[/bold blue]")
    try:
        subprocess.run([shellcheck_exec] + files, check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def lint(
    staged: bool = typer.Option(True, "--staged/--no-staged", help="Lint staged files only (default)."),
    base: str = typer.Option(None, "--base", help="Lint files changed relative to this base branch."),
    check_all: bool = typer.Option(False, "--all", help="Lint all files in the agent codebase."),
):
    """
    Lint the agent codebase using ruff (Python) and shellcheck (Shell).
    
    Default behavior is to lint only staged files.
    """
    root_dir = Path(__file__).parent.parent.parent.parent # src/agent/commands -> src/agent -> src -> .agent
    # A bit fragile path resolution, let's rely on git root or CWD 
    # The agent is usually run from the repo root
    
    py_files = []
    sh_files = []

    if check_all:
        console.print("[bold]Linting all files...[/bold]")
        # Find all relevant files in .agent/src and .agent/bin
        # Assuming we are running from repo root
        if Path(".agent").exists():
             py_files.extend([str(p) for p in Path(".agent/src").rglob("*.py")])
             sh_files.extend([str(p) for p in Path(".agent/bin").rglob("agent")]) # The main binary
             sh_files.extend([str(p) for p in Path(".agent/lib").rglob("*.sh")])
        else:
             # Fallback if not running from root, though agent expects to be.
             console.print("[red]Could not find .agent directory. Are you in the repo root?[/red]")
             raise typer.Exit(1)
             
    else:
        # Determine changed files
        target_base = base
        # If --base is provided, it overrides staged
        changed_files = get_changed_files(base=target_base, staged_only=staged and not base)
        
        if not changed_files:
            console.print("[green]No changed files to lint.[/green]")
            raise typer.Exit(0)
            
        for f in changed_files:
            if f.endswith(".py"):
                py_files.append(f)
            elif f.endswith(".sh") or f.endswith("bin/agent"):
                sh_files.append(f)

    success = True
    
    if py_files:
        if not run_ruff(py_files):
            success = False
    
    if sh_files:
        if not run_shellcheck(sh_files):
            success = False
            
    if not success:
        console.print("[bold red]Linting failed.[/bold red]")
        raise typer.Exit(1)
    else:
        console.print("[bold green]Linting passed.[/bold green]")

