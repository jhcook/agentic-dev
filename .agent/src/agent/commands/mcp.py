import asyncio
import json
import logging
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from agent.core.config import config, DEFAULT_MCP_SERVERS
from agent.core.mcp import MCPClient
from agent.core.secrets import get_secret, get_secret_manager

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="mcp",
    help="Manage and interact with MCP servers.",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()

def _get_server_config(server_name: str) -> dict:
    """Get server configuration merged with defaults."""
    # 1. Load from agent.yaml (user config)
    try:
        user_config = config.load_yaml(config.etc_dir / "agent.yaml")
        servers = config.get_value(user_config, "agent.mcp.servers") or {}
        if server_name in servers:
            return servers[server_name]
    except Exception:
        pass

    # 2. Check defaults
    if server_name in DEFAULT_MCP_SERVERS:
        return DEFAULT_MCP_SERVERS[server_name]
    
    raise typer.Exit(code=1)

def _get_github_token() -> str:
    """Retrieve GitHub token from secrets -> env -> gh CLI."""
    # 1. Try fetching (env or unlocked secret)
    token = get_secret("token", "github")
    if not token:
        token = get_secret("api_key", "gh")
    
    if token:
        return token

    # 2. Check gh CLI (Common fallback for workflows/locked secrets)
    # We try this BEFORE prompting for unlock, because if gh is logged in,
    # we don't want to block automation/user flow.
    import subprocess
    import shutil
    
    if shutil.which("gh"):
        try:
             # Run `gh auth token`
             result = subprocess.run(
                 ["gh", "auth", "token"], 
                 capture_output=True, 
                 text=True
             )
             if result.returncode == 0:
                 gh_token = result.stdout.strip()
                 if gh_token:
                     return gh_token
        except Exception:
             pass

    # 3. If not found, check if we need to unlock (last resort)
    manager = get_secret_manager()
    if manager.is_initialized() and not manager.is_unlocked():
        console.print("[yellow]GitHub token not found in environment or 'gh' CLI.[/yellow]")
        console.print("[dim]It might be in the secure store. Please unlock to check.[/dim]")
        from agent.commands.secret import _prompt_password
        
        for attempt in range(3):
            try:
                password = _prompt_password(confirm=False)
                manager.unlock(password)
                console.print("[green]unlocked[/green]")
                
                # Retry fetch
                token = manager.get_secret("github", "token")
                # If unlocked successfully, stop retrying
                break 
            except Exception as e:
                attempts_left = 2 - attempt
                if attempts_left > 0:
                     console.print(f"[bold red]Unlock failed:[/bold red] {e}. {attempts_left} attempts remaining.")
                else:
                     console.print(f"[bold red]Unlock failed:[/bold red] {e}.")
    
    # 4. Retry after unlock attempt
    if not token:
         token = get_secret("token", "github")
         
    if not token:
        console.print("[bold red]Error:[/bold red] GitHub token not found.")
        console.print("Run 'agent secret set github token', set GITHUB_PERSONAL_ACCESS_TOKEN, or 'gh auth login'.")
        raise typer.Exit(code=1)
        
    return token

@app.command(name="list-tools")
def list_tools(
    server: str = typer.Argument(..., help="Server name (e.g., github)")
):
    """
    List tools available on an MCP server.
    """
    server_config = _get_server_config(server)
    command = server_config["command"]
    args = server_config["args"]
    env = server_config.get("env", {})

    # Inject secrets if needed
    if server == "github":
        token = _get_github_token()
        env["GITHUB_PERSONAL_ACCESS_TOKEN"] = token

    client = MCPClient(command, args, env)
    
    try:
        tools = asyncio.run(client.list_tools())
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Failed to list tools: {e}")
        raise typer.Exit(code=1)

    table = Table(title=f"Tools on {server}")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="dim")
    
    for tool in tools:
        table.add_row(tool.name, tool.description or "")
    
    console.print(table)

async def _run_tool_internal(server: str, tool: str, args_str: str) -> None:
    """Internal shared logic for running a tool."""
    server_config = _get_server_config(server)
    command = server_config["command"]
    args_list = server_config["args"]
    env = server_config.get("env", {})

    if server == "github":
        token = _get_github_token()
        env["GITHUB_PERSONAL_ACCESS_TOKEN"] = token

    try:
        tool_args = json.loads(args_str)
    except json.JSONDecodeError:
        console.print("[bold red]Error:[/bold red] Invalid JSON arguments.")
        return

    client = MCPClient(command, args_list, env)
    
    import traceback
    
    try:
        result = await client.call_tool(tool, tool_args)
        # Result output handling
        console.print(result) # Raw output for now
    except BaseException as e:
        # Ignore KeyboardInterrupt to allow user to break
        if isinstance(e, KeyboardInterrupt):
            raise e
            
        # If it's typer.Exit, just re-raise (will be caught by start_session or exit run_tool)
        if isinstance(e, typer.Exit):
            raise e
            
        # Try to find McpError in ExceptionGroups (BaseExceptionGroup or ExceptionGroup)
        found_mcp_error = None
        
        # Check recursively if it's an ExceptionGroup
        queue = [e]
        while queue:
            curr = queue.pop(0)
            # Check by class name to avoid importing McpError if optional
            if type(curr).__name__ == "McpError":
                found_mcp_error = curr
                break
            if hasattr(curr, "exceptions"):
                queue.extend(curr.exceptions)
        
        if found_mcp_error:
             console.print(f"[bold red]MCP Error:[/bold red] {found_mcp_error}")
        else:
            console.print(f"[bold red]Error:[/bold red] Tool execution failed: {e}")
            console.print("[dim]Traceback:[/dim]")
            traceback.print_exc()
        
        # Re-raise to let caller handle if crucial
        raise e

@app.command(name="run")
def run_tool(
    server: str = typer.Argument(..., help="Server name"),
    tool: str = typer.Argument(..., help="Tool name"),
    args: str = typer.Option("{}", help="JSON arguments for the tool")
):
    """
    Run a specific tool on an MCP server.
    """
    try:
        asyncio.run(_run_tool_internal(server, tool, args))
    except (typer.Exit, SystemExit):
        raise
    except Exception:
        raise typer.Exit(code=1)

@app.command(name="start")
def start_session(
    server: str = typer.Argument(..., help="Server name")
):
    """
    Start an interactive session with an MCP server (REPL).
    """
    console.print(f"[dim]Starting interactive session with {server}...[/dim]")
    
    while True:
        try:
            tool_name = typer.prompt("Tool")
            if tool_name in ("exit", "quit"):
                break
            
            if tool_name == "help":
                 console.print("\n[bold]Available Commands:[/bold]")
                 console.print("  [cyan]help[/cyan]       Show this help message")
                 console.print("  [cyan]exit, quit[/cyan] Exit the session")
                 console.print("\n[bold]To list server tools, run:[/bold]")
                 console.print(f"  agent mcp list-tools {server}")
                 continue

            args_str = typer.prompt("Args (JSON)", default="{}")
            
            try:
                # We need to run async logic in sync context
                asyncio.run(_run_tool_internal(server, tool_name, args_str))
            except (Exception, typer.Exit, SystemExit):
                # _run_tool_internal prints the error, we just continue the loop
                # Catching SystemExit/typer.Exit here keeps the REPL alive!
                pass
            
        except (KeyboardInterrupt, EOFError):
            break
