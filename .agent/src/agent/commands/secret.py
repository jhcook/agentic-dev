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

"""
Secret Management CLI Commands.

Provides commands for managing encrypted secrets in .agent/secrets/.
"""

import getpass
import logging
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from agent.core.secrets import (
    SERVICE_ENV_MAPPINGS,
    InvalidPasswordError,
    SecretManager,
    SecretManagerError,
    get_secret_manager,
)

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="secret",
    help="Manage encrypted secrets for API keys and credentials.",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()


def _prompt_password(confirm: bool = False) -> str:
    """Prompt for master password securely."""
    password = getpass.getpass("Master password: ")
    
    if confirm:
        password2 = getpass.getpass("Confirm password: ")
        if password != password2:
            console.print("[bold red]Error:[/bold red] Passwords do not match.")
            raise typer.Exit(code=1)
    
    return password


def _validate_password_strength(password: str) -> bool:
    """Validate master password meets minimum requirements."""
    if len(password) < 12:
        console.print(
            "[bold red]Error:[/bold red] Password must be at least 12 characters."
        )
        return False
    
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    
    if not (has_upper and has_lower and has_digit):
        console.print(
            "[bold red]Error:[/bold red] Password must contain uppercase, "
            "lowercase, and numbers."
        )
        return False
    
    return True


def _unlock_manager(manager: SecretManager) -> None:
    """Unlock the secret manager with password prompt."""
    if manager.is_unlocked():
        return
    
    password = _prompt_password()
    try:
        manager.unlock(password)
    except InvalidPasswordError:
        console.print("[bold red]Error:[/bold red] Incorrect master password.")
        raise typer.Exit(code=1)


@app.command(name="init")
def init():
    """
    Initialize secret management with master password.
    
    Creates the .agent/secrets/ directory and sets up encrypted storage.
    """
    manager = get_secret_manager()
    
    if manager.is_initialized():
        console.print("[yellow]Secret manager already initialized.[/yellow]")
        raise typer.Exit(code=0)
    
    console.print("[bold]Initializing secret management...[/bold]")
    console.print("[dim]Your master password will encrypt all secrets.[/dim]")
    console.print("[dim]Requirements: 12+ chars, uppercase, lowercase, numbers[/dim]\n")
    
    password = _prompt_password(confirm=True)
    
    if not _validate_password_strength(password):
        raise typer.Exit(code=1)
    
    try:
        manager.initialize(password)
        console.print("\n[green]✅ Secret manager initialized successfully.[/green]")
        console.print(f"[dim]Secrets directory: {manager.secrets_dir}[/dim]")
    except SecretManagerError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="set")
def set_secret(
    service: str = typer.Argument(..., help="Service name (e.g., openai, supabase)"),
    key: str = typer.Argument(..., help="Secret key name (e.g., api_key)"),
    value: Optional[str] = typer.Option(
        None, "--value", "-v",
        help="Secret value (will prompt if not provided)"
    ),
):
    """
    Set a secret value.
    
    Example: agent secret set openai api_key --value sk-xxx
    """
    manager = get_secret_manager()
    
    if not manager.is_initialized():
        console.print(
            "[bold red]Error:[/bold red] Secret manager not initialized. "
            "Run 'agent secret init' first."
        )
        raise typer.Exit(code=1)
    
    _unlock_manager(manager)
    
    # Prompt for value if not provided
    if value is None:
        value = getpass.getpass(f"Enter value for {service}.{key}: ")
    
    if not value:
        console.print("[bold red]Error:[/bold red] Value cannot be empty.")
        raise typer.Exit(code=1)
    
    try:
        manager.set_secret(service, key, value)
        console.print(f"[green]✅ Secret '{service}.{key}' saved successfully.[/green]")
    except SecretManagerError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="get")
def get_secret(
    service: str = typer.Argument(..., help="Service name"),
    key: str = typer.Argument(..., help="Secret key name"),
    show: bool = typer.Option(
        False, "--show", "-s",
        help="Display unmasked value"
    ),
):
    """
    Get a secret value.
    
    Example: agent secret get openai api_key --show
    """
    manager = get_secret_manager()
    
    if not manager.is_initialized():
        console.print(
            "[bold red]Error:[/bold red] Secret manager not initialized. "
            "Run 'agent secret init' first."
        )
        raise typer.Exit(code=1)
    
    _unlock_manager(manager)
    
    try:
        value = manager.get_secret(service, key)
        
        if value is None:
            console.print(f"[yellow]Secret '{service}.{key}' not found.[/yellow]")
            raise typer.Exit(code=1)
        
        if show:
            console.print(value)
        else:
            # Show masked value
            masked = value[:4] + "***" + value[-4:] if len(value) > 8 else "***"
            console.print(f"[dim]{masked}[/dim]")
            console.print("[dim]Use --show to reveal full value[/dim]")
    
    except SecretManagerError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="list")
def list_secrets(
    service: Optional[str] = typer.Argument(
        None,
        help="Service to list (optional, lists all if omitted)"
    ),
):
    """
    List all secrets (values masked).
    
    Example: agent secret list
    Example: agent secret list openai
    """
    manager = get_secret_manager()
    
    if not manager.is_initialized():
        console.print(
            "[bold red]Error:[/bold red] Secret manager not initialized. "
            "Run 'agent secret init' first."
        )
        raise typer.Exit(code=1)
    
    secrets = manager.list_secrets(service)
    
    if not secrets:
        console.print("[yellow]No secrets found.[/yellow]")
        return
    
    table = Table(title="Stored Secrets")
    table.add_column("Service", style="cyan")
    table.add_column("Key", style="green")
    table.add_column("Value", style="dim")
    
    for svc, keys in sorted(secrets.items()):
        for key, value in sorted(keys.items()):
            table.add_row(svc, key, value)
    
    console.print(table)


@app.command(name="delete")
def delete_secret(
    service: str = typer.Argument(..., help="Service name"),
    key: str = typer.Argument(..., help="Secret key name"),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Skip confirmation"
    ),
):
    """
    Delete a secret.
    
    Example: agent secret delete openai api_key
    """
    manager = get_secret_manager()
    
    if not manager.is_initialized():
        console.print(
            "[bold red]Error:[/bold red] Secret manager not initialized."
        )
        raise typer.Exit(code=1)
    
    _unlock_manager(manager)
    
    if not force:
        confirm = typer.confirm(f"Delete secret '{service}.{key}'?")
        if not confirm:
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(code=0)
    
    try:
        deleted = manager.delete_secret(service, key)
        if deleted:
            console.print(f"[green]✅ Secret '{service}.{key}' deleted.[/green]")
        else:
            console.print(f"[yellow]Secret '{service}.{key}' not found.[/yellow]")
    except SecretManagerError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="import")
def import_secrets(
    service: str = typer.Argument(
        ..., help="Service to import (e.g., supabase, openai)"
    ),
):
    """
    Import secrets from environment variables.
    
    Reads configured environment variables and stores them encrypted.
    
    Example: agent secret import supabase
    Example: agent secret import openai
    """
    manager = get_secret_manager()
    
    if not manager.is_initialized():
        console.print(
            "[bold red]Error:[/bold red] Secret manager not initialized. "
            "Run 'agent secret init' first."
        )
        raise typer.Exit(code=1)
    
    if service not in SERVICE_ENV_MAPPINGS:
        console.print(f"[bold red]Error:[/bold red] Unknown service: {service}")
        services = ', '.join(SERVICE_ENV_MAPPINGS.keys())
        console.print(f"[dim]Available services: {services}[/dim]")
        raise typer.Exit(code=1)
    
    _unlock_manager(manager)
    
    console.print(f"[dim]Importing secrets for {service}...[/dim]")
    
    try:
        count = manager.import_from_env(service)
        
        if count > 0:
            console.print(
                f"[green]✅ Imported {count} secret(s) for {service}.[/green]"
            )
        else:
            console.print(
                f"[yellow]No environment variables found for {service}.[/yellow]"
            )
            expected = list(SERVICE_ENV_MAPPINGS[service].values())
            console.print(f"[dim]Expected: {expected}[/dim]")
    
    except SecretManagerError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="export")
def export_secrets(
    service: str = typer.Argument(..., help="Service to export"),
    output: Optional[str] = typer.Option(
        None, "--output", "-o",
        help="Output file (default: stdout)"
    ),
):
    """
    Export secrets as environment variable format.
    
    Example: agent secret export supabase
    Example: agent secret export openai -o .env.local
    """
    manager = get_secret_manager()
    
    if not manager.is_initialized():
        console.print(
            "[bold red]Error:[/bold red] Secret manager not initialized."
        )
        raise typer.Exit(code=1)
    
    _unlock_manager(manager)
    
    try:
        env_vars = manager.export_to_env(service)
        
        if not env_vars:
            console.print(f"[yellow]No secrets found for {service}.[/yellow]")
            raise typer.Exit(code=1)
        
        lines = [f"{key}={value}" for key, value in env_vars.items()]
        content = "\n".join(lines) + "\n"
        
        if output:
            with open(output, "w") as f:
                f.write(content)
            console.print(f"[green]✅ Exported to {output}[/green]")
        else:
            # Print to stdout (for piping)
            print(content, end="")
    
    except SecretManagerError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="services")
def list_services():
    """
    List available services and their environment variable mappings.
    """
    table = Table(title="Supported Services")
    table.add_column("Service", style="cyan")
    table.add_column("Key", style="green")
    table.add_column("Environment Variables", style="dim")
    
    for service, keys in sorted(SERVICE_ENV_MAPPINGS.items()):
        for key, env_vars in sorted(keys.items()):
            table.add_row(service, key, ", ".join(env_vars))
    
    console.print(table)


@app.command(name="login")
def login_secrets(
    password: Optional[str] = typer.Option(
        None, "--password", "-p",
        help="Master password (will prompt if not provided)"
    ),
):
    """
    Store master password in system keychain for auto-unlocking.
    
    Allows headless execution of agent commands without prompts.
    """
    try:
        import keyring
    except ImportError:
        console.print(
            "[bold red]Error:[/bold red] 'keyring' library not installed. "
            "Run 'pip install keyring' first."
        )
        raise typer.Exit(code=1)

    manager = get_secret_manager()
    
    if not manager.is_initialized():
        console.print(
            "[bold red]Error:[/bold red] Secret manager not initialized. "
            "Run 'agent secret init' first."
        )
        raise typer.Exit(code=1)
    
    # Get and verify password
    if password:
        # Verify provided password
        try:
            manager.unlock(password)
        except InvalidPasswordError:
             console.print("[bold red]Error:[/bold red] Incorrect master password.")
             raise typer.Exit(code=1)
    else:
        # Prompt explicitly
        console.print("Enter master password to store in keychain:")
        password = _prompt_password()
        try:
             manager.unlock(password)
        except InvalidPasswordError:
             console.print("[bold red]Error:[/bold red] Incorrect master password.")
             raise typer.Exit(code=1)

    # Store in keyring
    try:
        keyring.set_password("agent-cli", "master_key", password)
        console.print(
            "[green]✅ Master password stored in system keychain.[/green]"
        )
        console.print(
            "[dim]The agent will now auto-unlock using the keychain.[/dim]"
        )
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Failed to write to keychain: {e}")
        raise typer.Exit(code=1)


@app.command(name="logout")
def logout_secrets():
    """
    Remove master password from system keychain.
    """
    try:
        import keyring
        try:
            keyring.delete_password("agent-cli", "master_key")
            console.print("[green]✅ Master password removed from keychain.[/green]")
        except keyring.errors.PasswordDeleteError:
             console.print("[yellow]No password found in keychain.[/yellow]")
    except ImportError:
         console.print("[red]Keyring library not available.[/red]")
         raise typer.Exit(code=1)

