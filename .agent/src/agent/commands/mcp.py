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

import asyncio
import json
import logging
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from agent.core.config import config, DEFAULT_MCP_SERVERS
from agent.core.mcp import MCPClient
from agent.core.secrets import get_secret, get_secret_manager, SecretManager
from opentelemetry import trace
import subprocess
import shutil
from rich.prompt import Confirm


logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

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
    elif server == "notebooklm":
        notebooklm_cookies = get_secret("cookies", "notebooklm")
        if notebooklm_cookies:
            env["NOTEBOOKLM_COOKIES"] = notebooklm_cookies

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
    elif server == "notebooklm":
        notebooklm_cookies = get_secret("cookies", "notebooklm")
        if notebooklm_cookies:
            env["NOTEBOOKLM_COOKIES"] = notebooklm_cookies

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

@app.command(name="auth")
def authenticate_server(
    server: str = typer.Argument(..., help="Server name (e.g., notebooklm)"),
    file: Optional[str] = typer.Option(None, "--file", help="Use file-based cookie import from the provided path instead of launching Chrome"),
    auto: bool = typer.Option(False, "--auto", help="Automatically extracts session cookies from a supported local browser using the OS-native keychain (no DevTools needed)"),
    no_auto_launch: bool = typer.Option(False, "--no-auto-launch", help="Provide instructions for manual browser cookie extraction without launching the interactive script"),
    clear_session: bool = typer.Option(False, "--clear-session", help="Clear the saved authentication session cookies for this server")
) -> None:
    """
    Authenticate with an MCP server (e.g., notebooklm).

    For the 'notebooklm' server, this command supports several authentication flows:
    - --auto: Automatically extract your active session cookies from a local browser.
    - --file <path>: Import cookies from a saved JSON file.
    - --no-auto-launch: Print instructions for manual cookie extraction.
    - --clear-session: Delete the securely stored NotebookLM cookies.
    
    Security: NotebookLM relies on Google session cookies which are highly sensitive. 
    They are stored encrypted in the OS keyring and never written to disk in plain text.
    """
    with tracer.start_as_current_span("mcp.authenticate_server") as span:
        span.set_attribute("server.name", server)
        if server == "notebooklm":
            logger.info("Starting NotebookLM authentication flow...")
            
            if clear_session:
                sm = SecretManager()
                if sm.is_initialized() and not sm.is_unlocked():
                    try:
                        from agent.commands.secret import _prompt_password
                        password = _prompt_password(confirm=False)
                        sm.unlock(password)
                    except Exception as e:
                        logger.error(f"Failed to unlock SecretManager: {e}")
                        raise typer.Exit(code=1)
                
                if sm.is_unlocked() and sm.has_secret("notebooklm", "cookies"):
                    sm.delete_secret("notebooklm", "cookies")
                    logger.info("Successfully cleared NotebookLM session cookies from secure storage.")
                else:
                    logger.info("No NotebookLM session cookies found to clear.")
                return

            
            if no_auto_launch:
                logger.info("Manual extraction instructions:")
                logger.info("1. Open your browser and go to https://notebooklm.google.com")
                logger.info("2. Open Developer Tools -> Application/Storage -> Cookies")
                logger.info("3. Copy the values of SID, HSID, and SSID")
                logger.info("4. Save them to a JSON file and run: agent mcp auth notebooklm --file <path>")
                return

            if auto:
                logger.error("Auto cookie extraction (--auto) is disabled pending a full GDPR compliance review.")
                logger.error("Please use the standard interactive method or supply cookies via --file.")
                raise typer.Exit(code=1)
                
                with tracer.start_as_current_span("notebooklm.auto_extract"):
                    consent = Confirm.ask(
                        "[bold yellow]WARNING (GDPR Informed Consent):[/bold yellow]\n"
                        "This action will read your highly sensitive active Google session cookies (`SID`, `HSID`, `SSID`) "
                        "from your local browser to authenticate with NotebookLM.\n"
                        "These cookies can grant broad access to your Google Account.\n"
                        "They will be briefly processed in memory and subsequently stored securely using encrypted system keychains (SecretManager). "
                        "No plain text cookies will be written to disk. "
                        "Do you explicitly consent to this processing?",
                        default=False
                    )
                    
                    if not consent:
                        logger.warning("Cookie extraction aborted by user.")
                        raise typer.Exit(code=1)

                    logger.info("Attempting automatic extraction... (your OS may prompt you for your Keychain/Keyring password)")
                    
                    # Use pinned version and output JSON for parsing
                    script = """
import sys
import json
import time

try:
    import browser_cookie3
except ImportError:
    print(json.dumps({"status": "error", "message": "browser-cookie3 not installed."}))
    sys.exit(1)

browsers = [
    ("Chrome", browser_cookie3.chrome),
    ("Chromium", browser_cookie3.chromium),
    ("Brave", browser_cookie3.brave),
    ("Edge", browser_cookie3.edge),
    ("Vivaldi", browser_cookie3.vivaldi),
    ("Firefox", browser_cookie3.firefox)
]

cookie_dict = {}
found_browser = None

for name, func in browsers:
    try:
        cookies = func(domain_name=".google.com")
        temp_dict = {c.name: c.value for c in cookies}
        
        required = ["SID", "HSID", "SSID"]
        missing = [r for r in required if r not in temp_dict]
        
        if not missing:
            cookie_dict = {k: temp_dict[k] for k in required}
            found_browser = name
            break
    except Exception as e:
        pass

if not cookie_dict:
    print(json.dumps({"status": "error", "message": "Could not find required NotebookLM cookies."}))
    sys.exit(1)

print(json.dumps({
    "status": "success", 
    "browser": found_browser, 
    "cookies": cookie_dict
}))
"""
                    try:
                        # Need to use check=False to read stdout even if script exits 1
                        result = subprocess.run(
                            ["uv", "run", "--with", "browser-cookie3==0.20.1", "python", "-c", script],
                            capture_output=True,
                            text=True
                        )
                        
                        try:
                            stdout_str = result.stdout.strip()
                            json_str = stdout_str
                            
                            # Extract just the JSON object from stdout in case there's preceding text
                            start = stdout_str.find('{')
                            end = stdout_str.rfind('}')
                            if start != -1 and end != -1 and end > start:
                                json_str = stdout_str[start:end+1]
                                
                            if not json_str:
                                raise json.JSONDecodeError("Empty extracted JSON output", stdout_str, 0)
                                
                            output = json.loads(json_str)
                            if output.get("status") == "success":
                                cookies = output.get("cookies", {})
                                browser = output.get("browser", "unknown")
                                
                                # Store using SecretManager
                                sm = SecretManager()
                                if sm.is_initialized() and not sm.is_unlocked():
                                    try:
                                        from agent.commands.secret import _prompt_password
                                        password = _prompt_password(confirm=False)
                                        sm.unlock(password)
                                    except Exception as e:
                                        logger.error(f"Failed to unlock SecretManager: {e}")
                                        raise typer.Exit(code=1)
                                        
                                with tracer.start_as_current_span("notebooklm.store_cookies"):
                                    # Note: In a real implementation we might exchange cookies for an API token.
                                    # Since we must persist the cookies for MCP, we store them encrypted via SecretManager.
                                    sm.set_secret("notebooklm", "cookies", json.dumps(cookies))
                                
                                logger.info(
                                    "SUCCESS! Cookies extracted and securely stored.", 
                                    extra={"browser": browser, "cookie_count": len(cookies)}
                                )
                                return
                            else:
                                logger.error(f"Auto-extraction failed: {output.get('message')}")
                                logger.warning("Try using the standard interactive method without --auto.")
                                raise typer.Exit(code=1)
                        except json.JSONDecodeError:
                            logger.error("Auto-extraction failed to parse output.")
                            logger.error(result.stderr) # Safely print stderr, exclude stdout to prevent PII leak
                            raise typer.Exit(code=1)
                            
                    except FileNotFoundError:
                        logger.error("Error: 'uv' command not found. Please install uv.")
                        raise typer.Exit(code=1)

            try:
                # We run this interactively so the user can see the browser and the prompts
                with tracer.start_as_current_span("notebooklm.interactive_auth"):
                    cmd = ["uv", "tool", "run", "--from", "notebooklm-mcp-server", "notebooklm-mcp-auth"]
                    if file:
                        cmd.extend(["--file", str(file)])
                        
                    subprocess.run(
                        cmd,
                        check=True
                    )
            except subprocess.CalledProcessError as e:
                logger.error(f"Authentication failed with exit code {e.returncode}.")
                raise typer.Exit(code=e.returncode)
            except FileNotFoundError:
                logger.error("Error: 'uv' command not found. Please install uv.")
                raise typer.Exit(code=1)

        elif server == "github":
            logger.warning("GitHub MCP does not have a dedicated auth command.")
            logger.info("Please set GITHUB_PERSONAL_ACCESS_TOKEN or run 'gh auth login'.")
        else:
            # Check if it's a known server without a specific auth flow
            try:
                _get_server_config(server)
                logger.warning(f"No dedicated authentication command for '{server}'.")
            except typer.Exit:
                 logger.error(f"Error: Unknown server '{server}'.")
                 raise typer.Exit(code=1)

