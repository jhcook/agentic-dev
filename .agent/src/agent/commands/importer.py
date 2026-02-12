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
from pathlib import Path
import typer
from rich.console import Console

console = Console()
app = typer.Typer(help="Import assets (tools, docs, etc.) into the agent system.")

@app.command(name="tool")
def import_tool(
    source: str = typer.Argument(..., help="Path or name of the tool file in the custom directory"),
    name: str = typer.Option(None, "--name", "-n", help="Optional custom name for the tool")
):
    """
    Import a custom tool into the Voice Agent's tool registry.
    If only a name is provided, looks in the project root './custom/' directory.
    """
    source_path = Path(source)
    
    # Heuristic: If it's just a name, look in root ./custom/
    if not source_path.exists():
        # Try root/custom/<name>
        alt_path = Path("custom") / source
        if alt_path.suffix != ".py" and not alt_path.exists():
             alt_path = Path("custom") / (source + ".py")

        if alt_path.exists():
            source_path = alt_path
        else:
             console.print(f"[bold red]Error: Tool '{source}' not found directly or in './custom/'.[/bold red]")
             raise typer.Exit(1)
        
    if not source_path.suffix == ".py":
        console.print("[bold red]Error: Only Python (.py) tools can be imported.[/bold red]")
        raise typer.Exit(1)
        
    # Target directory: .agent/src/backend/voice/tools/custom
    target_dir = Path(".agent/src/backend/voice/tools/custom")
    target_dir.mkdir(parents=True, exist_ok=True)
    
    target_name = name if name else source_path.name
    if not target_name.endswith(".py"):
        target_name += ".py"
        
    target_path = target_dir / target_name
    
    try:
        shutil.copy2(source_path, target_path)
        console.print(f"[bold green]Successfully imported tool to:[/bold green] {target_path}")
        console.print("[dim]The Voice Agent will hot-reload this tool automatically.[/dim]")
    except Exception as e:
        console.print(f"[bold red]Error importing tool:[/bold red] {e}")
        raise typer.Exit(1)
