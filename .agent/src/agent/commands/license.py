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

import os
import subprocess
from pathlib import Path
import typer
from rich.console import Console

from agent.core.utils import get_full_license_header

console = Console()
app = typer.Typer(help="Manage file license headers.")

def apply_license_to_file(filepath: Path) -> bool:
    """Applies the copyright header to a specific file if appropriate. Returns True if modified."""
    if not filepath.exists() or not filepath.is_file():
        return False
        
    if filepath.suffix not in [".py", ".yaml", ".yml"]:
        return False

    target_header = get_full_license_header().strip()

    try:
        content = filepath.read_text()
        
        if content.startswith(target_header):
            return False

        lines = content.splitlines()
        
        # If it has the old single-line header, remove it so we can upgrade it
        if lines and lines[0].strip() == "# Copyright 2026 Justin Cook":
            lines.pop(0)
            while lines and lines[0].strip() == "":
                lines.pop(0)
            content = "\n".join(lines)
            lines = content.splitlines()
            
        # Check if it has an existing copyright (that isn't the one we just removed)
        if lines and lines[0].startswith("# Copyright"):
            return False
            
        # Handle shebangs
        if lines and lines[0].startswith("#!"):
            new_content = lines[0] + "\n\n" + target_header + "\n\n" + "\n".join(lines[1:]).lstrip() + ("\n" if lines[1:] else "")
        else:
            new_content = target_header + "\n\n" + content.lstrip()
            
        filepath.write_text(new_content)
        return True
        
    except Exception as e:
        console.print(f"[yellow]Warning: Failed to process {filepath}: {e}[/yellow]")
        return False

@app.command("apply-license")
def apply_license(
    target_dir: str = typer.Argument(".", help="Directory to apply licenses to.")
):
    """
    Apply the copyright header to Python and YAML files in the target directory.
    """
    target_path = Path(target_dir).resolve()
    if not target_path.exists():
        console.print(f"[red]Error: Target directory {target_dir} does not exist.[/red]")
        raise typer.Exit(1)

    valid_extensions = {".py", ".yaml", ".yml"}
    candidate_files = []

    for root, dirs, files in os.walk(target_path):
        # Determine paths to skip
        # We modify dirs in-place to prune the walk
        dirs[:] = [d for d in dirs if not d.startswith('.') or d in ['.agent', '.github']]
        
        for file in files:
            filepath = Path(root) / file
            if filepath.suffix in valid_extensions:
                candidate_files.append(filepath)

    if not candidate_files:
        console.print("[bold green]No files to process.[/bold green]")
        return

    # Find ignored files in batches
    ignored_files = set()
    try:
        chunk_size = 100
        for i in range(0, len(candidate_files), chunk_size):
            chunk = candidate_files[i:i + chunk_size]
            result = subprocess.run(
                ["git", "check-ignore"] + [str(p) for p in chunk],
                capture_output=True,
                text=True
            )
            if result.stdout:
                for line in result.stdout.splitlines():
                    ignored_files.add(Path(line.strip()).resolve())
    except Exception as e:
        console.print(f"[yellow]Warning: git check-ignore failed ({e}). Proceeding without ignore list.[/yellow]")

    count = 0
    for filepath in candidate_files:
        if filepath.resolve() in ignored_files:
            continue
            
        if apply_license_to_file(filepath):
            try:
                console.print(f"[green]Added license header to {filepath.relative_to(target_path)}[/green]")
            except ValueError:
                console.print(f"[green]Added license header to {filepath}[/green]")
            count += 1
            
    console.print(f"[bold green]Successfully applied license header to {count} file(s).[/bold green]")