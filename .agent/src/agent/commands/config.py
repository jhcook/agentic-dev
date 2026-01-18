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
import typer
from rich.console import Console
from rich.syntax import Syntax

from agent.core.config import config

app = typer.Typer(
    name="config",
    help="Manage agent configuration.",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()

@app.command(name="get")
def get_config(
    key: str = typer.Argument(..., help="Configuration key (e.g. 'router.models.gpt-4o.tier')"),
    file: str = typer.Option(None, help="Specific configuration file to read from.")
):
    """
    Get a configuration value.
    If 'key' starts with a filename (e.g. 'router.'), searches that file.
    Otherwise, defaults to router.yaml unless --file is specified.
    """
    # 1. Determine target file and actual key
    target_file = "router.yaml"
    actual_key = key
    
    # Check for prefix routing (e.g. "agents.team")
    parts = key.split(".", 1)
    if len(parts) == 2:
        potential_file = f"{parts[0]}.yaml"
        if (config.etc_dir / potential_file).exists():
             target_file = potential_file
             actual_key = parts[1]

    # Override if --file is provided
    if file:
        target_file = file
        actual_key = key # Reset key if file explicitly provided? 
        # Actually standard behavior: if I say --file agents.yaml, key should probably be relative to it.
        # But if I say --file agents.yaml and key is agents.team... redundancy?
        # Let's trust prefix routing primarily, but --file forces a specific file.
        
    config_path = config.etc_dir / target_file
    
    try:
        data = config.load_yaml(config_path)
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] Config file '{target_file}' not found.")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Failed to load config: {e}")
        raise typer.Exit(code=1)

    value = config.get_value(data, actual_key)
    
    if value is None:
        console.print(f"[yellow]Key '{actual_key}' not found in '{target_file}' or value is null.[/yellow]")
        raise typer.Exit(code=1)

    if isinstance(value, (dict, list)):
        import yaml
        yaml_str = yaml.dump(value, default_flow_style=False, sort_keys=False)
        console.print(Syntax(yaml_str, "yaml", theme="monokai", word_wrap=True))
    else:
        console.print(str(value))


@app.command(name="set")
def set_config(
    key: str = typer.Argument(..., help="Configuration key (e.g. 'router.models.gpt-4o.tier')"),
    value: str = typer.Argument(..., help="Value to set"),
    file: str = typer.Option(None, help="Specific configuration file to modify.")
):
    """
    Set a configuration value.
    If 'key' starts with a filename (e.g. 'router.'), modifies that file.
    """
    # 1. Determine target file and actual key
    target_file = "router.yaml"
    actual_key = key
    
    parts = key.split(".", 1)
    if len(parts) == 2:
        potential_file = f"{parts[0]}.yaml"
        if (config.etc_dir / potential_file).exists():
             target_file = potential_file
             actual_key = parts[1]

    if file:
        target_file = file

    config_path = config.etc_dir / target_file
    
    # 2. Load
    try:
        data = config.load_yaml(config_path)
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] Config file '{target_file}' not found.")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Failed to load config: {e}")
        raise typer.Exit(code=1)

    old_value = config.get_value(data, actual_key)
    
    # 3. Backup
    try:
        backup = config.backup_config(config_path)
        if backup:
            console.print(f"[dim]Backup created:[/dim] {backup}")
    except Exception as e:
         console.print(f"[bold red]Warning:[/bold red] Failed to create backup: {e}")

    # 4. Set Value
    try:
        config.set_value(data, actual_key, value)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Failed to set value: {e}")
        raise typer.Exit(code=1)

    # 5. Save
    try:
        config.save_yaml(config_path, data)
        new_value = config.get_value(data, actual_key)
        
        # Audit logging for SOC2 compliance
        logging.info(
            f"Configuration change: file={target_file}, key={actual_key}, "
            f"old_value={old_value}, new_value={new_value}"
        )
        
        console.print(f"[green]Successfully updated '{actual_key}' in {target_file}.[/green]")
        if old_value is not None:
             console.print(f"Old value: {old_value}")
        console.print(f"New value: {new_value}")
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Failed to save config: {e}")
        raise typer.Exit(code=1)


@app.command(name="list")
def list_config(
    file: str = typer.Option(None, help="Specific configuration file to list (in .agent/etc/)")
):
    """
    List configuration. If no file is specified, lists all valid YAML files in .agent/etc.
    """
    import yaml
    
    files_to_list = []
    
    if file:
        files_to_list = [config.etc_dir / file]
    else:
        # Scan dir
        files_to_list = sorted(list(config.etc_dir.glob("*.yaml")) + list(config.etc_dir.glob("*.yml")))

    if not files_to_list:
        console.print("[yellow]No configuration files found.[/yellow]")
        return

    for config_path in files_to_list:
        if not config_path.exists():
             console.print(f"[bold red]Error:[/bold red] Config file '{config_path.name}' not found.")
             continue
             
        # Header
        console.print(f"\n[bold blue]### {config_path.name} ###[/bold blue]")
        
        try:
            data = config.load_yaml(config_path)
            yaml_str = yaml.dump(data, default_flow_style=False, sort_keys=False)
            console.print(Syntax(yaml_str, "yaml", theme="monokai", word_wrap=True))
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] Failed to load config: {e}")
