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

import shutil
import subprocess
import sys
import os
from pathlib import Path
from typing import List, Optional, Set
from opentelemetry import trace

import typer
from rich.console import Console

console = Console()


def get_all_files(path: Path) -> List[Path]:
    """
    Get all files in path recursively, respecting gitignore if possible.
    """
    files = []

    # Check if inside git repo
    try:
        cmd = ["git", "ls-files", "--full-name"]

        cwd = path if path.is_dir() else path.parent
        if not cwd.exists():
            return []

        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, check=True
        )
        git_files = [f.strip() for f in result.stdout.splitlines() if f.strip()]

        for f in git_files:
            abs_path = cwd / f
            if path.is_dir():
                if str(abs_path).startswith(str(path.resolve())):
                    files.append(abs_path)
            else:
                files.append(abs_path)

        if not files and not (cwd / ".git").exists():
            files.extend([p for p in path.rglob("*") if p.is_file()])

    except (subprocess.CalledProcessError, FileNotFoundError):
        for p in path.rglob("*"):
            if p.is_file():
                parts = p.parts
                if (
                    ".git" in parts
                    or "node_modules" in parts
                    or "__pycache__" in parts
                    or ".venv" in parts
                ):
                    continue
                files.append(p)

    return files


def get_files_to_lint(
    path: Optional[Path], all_files: bool, base: Optional[str], staged: bool
) -> List[str]:
    """
    Determine which files to lint based on arguments.
    """
    candidates: Set[str] = set()
    cwd = Path.cwd()

    if path:
        target = path.resolve()
        if target.is_file():
            candidates.add(str(target))
        elif target.is_dir():
            found = get_all_files(target)
            candidates.update(str(f) for f in found)
        else:
            console.print(f"[red]Path not found: {target}[/red]")
            raise typer.Exit(1)

    elif all_files:
        found = get_all_files(cwd)
        candidates.update(str(f) for f in found)

    else:
        cmd = ["git", "diff", "--name-only", "--diff-filter=d"]

        if base:
            cmd.extend([f"{base}...HEAD"])
        elif staged:
            cmd.append("--cached")
        else:
            cmd.append("--cached")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            rel_files = [f.strip() for f in result.stdout.splitlines() if f.strip()]

            root_res = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
            )
            if root_res.returncode == 0:
                git_root = Path(root_res.stdout.strip())
                for rf in rel_files:
                    abs_p = git_root / rf
                    if abs_p.exists():
                        candidates.add(str(abs_p))
        except subprocess.CalledProcessError:
            console.print(
                "[yellow]Not a git repository or git error. Falling back to all "
                "files.[/yellow]"
            )
            return []

    return sorted(list(candidates))


def run_ruff(files: List[str], fix: bool = False) -> bool:
    if not files:
        return True
    console.print(f"[bold blue]Running ruff on {len(files)} files...[/bold blue]")
    cmd = [sys.executable, "-m", "ruff", "check"]
    if fix:
        cmd.append("--fix")
    cmd.extend(files)
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def run_shellcheck(files: List[str], fix: bool = False) -> bool:
    if not files:
        return True
    shellcheck = shutil.which("shellcheck")
    if not shellcheck:
        console.print("[yellow]Warning: shellcheck not found. Skipping.[/yellow]")
        return True

    console.print(f"[bold blue]Running shellcheck on {len(files)} files...[/bold blue]")
    if fix:
        console.print("[yellow]Note: Shellcheck does not support auto-fix via CLI.[/yellow]")
    
    try:
        subprocess.run([shellcheck] + files, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def find_eslint_root(file_path: Path) -> Path:
    """Find the directory containing eslint config for a file."""
    current = file_path.parent
    while current != current.parent:
        if (
            (current / "eslint.config.js").exists()
            or (current / "eslint.config.mjs").exists()
            or (current / "eslint.config.cjs").exists()
            or (current / ".eslintrc.js").exists()
            or (current / ".eslintrc.json").exists()
        ):
            return current
        if (current / "package.json").exists():
             # package.json might contain eslintConfig
             # Check if we are at the top of a sub-project (like web/)
             # If we hit .git without finding config, we might stop there.
             pass
        
        if (current / ".git").exists():
            return current
            
        current = current.parent
    return Path.cwd()


def run_eslint(files: List[str], fix: bool = False) -> bool:
    if not files:
        return True

    # Group files by project root
    groups = {}
    for f in files:
        p = Path(f).resolve()
        root = find_eslint_root(p)
        if root not in groups:
            groups[root] = []
        
        try:
            rel = p.relative_to(root)
            groups[root].append(str(rel))
        except ValueError:
            groups[root].append(str(p))

    success = True
    
    for root, root_files in groups.items():
        console.print(f"[bold blue]Running eslint in {root} on {len(root_files)} files...[/bold blue]")

        cmd = ["npx", "--no-install", "eslint"]
        if fix:
            cmd.append("--fix")
        cmd.extend(root_files)

        try:
            subprocess.run(cmd, cwd=root, check=True)
        except subprocess.CalledProcessError:
            try:
                # Fallback to global/local binary if npx fails weirdly?
                # Or maybe npx failed because valid eslint not found in tree.
                fallback_cmd = ["eslint"]
                if fix:
                    fallback_cmd.append("--fix")
                fallback_cmd.extend(root_files)
                subprocess.run(fallback_cmd, cwd=root, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                console.print(
                    f"[bold red]ESLint failed in {root}.[/bold red] Ensure "
                    "dependencies are installed (`npm install`)."
                )
                success = False
    
    return success


tracer = trace.get_tracer(__name__)



def run_markdownlint(files: List[str], fix: bool = False) -> bool:
    if not files:
        return True
    
    with tracer.start_as_current_span("lint.markdownlint") as span:
        span.set_attribute("file_count", len(files))
        
        # Check availability
        import shutil
        is_ci = os.getenv("CI", "").lower() in ("true", "1", "yes")
        
        has_npx = shutil.which("npx") is not None
        has_local = shutil.which("markdownlint") is not None
        
        if not has_npx and not has_local:
             if is_ci:
                 console.print("[bold red]❌ CI Error: markdownlint missing.[/bold red]")
                 span.set_attribute("status", "failed_ci")
                 return False
             console.print("[dim]⚠️  Skipping markdownlint.[/dim]")
             span.set_attribute("skipped", True)
             return True
             
        # Command Construction
        cmd = []
        if has_npx:
            cmd = ["npx", "--yes", "markdownlint-cli"]
        else:
            cmd = ["markdownlint"]
            
        if fix:
            cmd.append("--fix")
        cmd.extend(files)
        
        try:
            subprocess.run(cmd, check=True)
            span.set_attribute("status", "success")
            return True
        except subprocess.CalledProcessError:
             span.set_attribute("status", "failed")
             return False
        except Exception as e:
             span.set_attribute("status", "error")
             span.record_exception(e)
             console.print(f"[red]Error: {e}[/red]")
             return False




def lint(
    path: Optional[Path] = typer.Argument(
        None, help="Path to file or directory to lint."
    ),
    all_files: bool = typer.Option(
        False, "--all", help="Lint all files in the current directory recursively."
    ),
    base: str = typer.Option(
        None, "--base", help="Lint files changed relative to this base branch."
    ),
    staged: bool = typer.Option(
        True,
        "--staged/--no-staged",
        help="Lint staged files only (default if no path/all).",
    ),
    fix: bool = typer.Option(
        False, "--fix", help="Automatically fix lint errors where possible."
    ),
):
    """
    Lint the code using ruff (Python), shellcheck (Shell), and eslint (JS/TS).

    Default behavior (no args): Lints staged files.
    """

    files = get_files_to_lint(path, all_files, base, staged)

    if not files:
        console.print("[green]No files to lint.[/green]")
        raise typer.Exit(0)

    py_files = [f for f in files if f.endswith(".py")]
    sh_files = [f for f in files if f.endswith(".sh") or f.endswith("bin/agent")]
    js_files = [f for f in files if f.endswith((".js", ".jsx", ".ts", ".tsx"))]
    md_files = [f for f in files if f.endswith(".md")]

    success = True

    if py_files:
        if not run_ruff(py_files, fix=fix):
            success = False

    if sh_files:
        if not run_shellcheck(sh_files, fix=fix):
            success = False

    if js_files:
        if not run_eslint(js_files, fix=fix):
            success = False

    if md_files:
        if not run_markdownlint(md_files, fix=fix):
            success = False

    if not success:
        console.print("[bold red]Linting failed.[/bold red]")
        raise typer.Exit(1)
    else:
        console.print("[bold green]Linting passed.[/bold green]")
