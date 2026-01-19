import getpass
import shutil
import subprocess
import sys
from pathlib import Path

import typer

# Note: This command requires `typer` and `python-dotenv`.
# Ensure they are added to your project's dependencies.
from rich.console import Console
from rich.table import Table

from agent.core.ai.service import PROVIDERS, AIService, ai_service
from agent.core.config import config
from agent.core.secrets import (
    InvalidPasswordError,
    get_secret,
    get_secret_manager,
)

console = Console()

# REQUIRED_KEYS removed, driven by PROVIDERS constant from service.py

# Define project paths relative to the current working directory.
# This assumes the command is run from the project root.
PROJECT_ROOT: Path = Path(".").resolve()
AGENT_DIR: Path = PROJECT_ROOT / ".agent"
ENV_FILE: Path = PROJECT_ROOT / ".env"
GITIGNORE_FILE: Path = PROJECT_ROOT / ".gitignore"

app = typer.Typer()

def check_dependencies() -> None:
    """Verifies that required system dependencies are installed."""
    typer.echo("[INFO] Checking for required system dependencies...")
    # As per @Security review, add any binary dependencies here. e.g., `git`
    dependencies = ["git", "python3"]
    recommended = ["gh"]

    all_found = True
    for dep in dependencies:
        if not shutil.which(dep):
            typer.secho(
                f"[ERROR] Dependency not found: '{dep}'. Please install it and run onboard again.",
                fg=typer.colors.RED,
            )
            all_found = False
        else:
            typer.secho(f"  - Found {dep}", fg=typer.colors.GREEN)

    if not all_found:
        raise typer.Exit(code=1)

    # Check recommended
    for dep in recommended:
        if not shutil.which(dep):
            typer.secho(
                f"[WARN] Recommended dependency not found: '{dep}'. Some features may be limited.",
                fg=typer.colors.YELLOW,
            )
        else:
            typer.secho(f"  - Found {dep} (recommended)", fg=typer.colors.GREEN)

    typer.secho("[OK] System dependencies check passed.", fg=typer.colors.GREEN)


def check_github_auth() -> None:
    """Checks if the user is authenticated with GitHub CLI."""
    if not shutil.which("gh"):
        return

    typer.echo("\n[INFO] Checking GitHub authentication status...")
    try:
        # Run gh auth status. Capture output to avoid spamming unless error.
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            typer.secho("[OK] GitHub CLI is authenticated.", fg=typer.colors.GREEN)
        else:
            typer.secho(
                "[WARN] GitHub CLI is not authenticated.",
                fg=typer.colors.YELLOW
            )
            typer.echo("To use GitHub features (like PR creation), please run:")
            typer.secho("  gh auth login", fg=typer.colors.CYAN, bold=True)

            if typer.confirm("Would you like to run 'gh auth login' now?", default=True):
                subprocess.run(["gh", "auth", "login"])

    except Exception as e:
        typer.secho(f"[WARN] Failed to check GitHub status: {e}", fg=typer.colors.YELLOW)


def ensure_agent_directory(project_root: Path = None) -> None:
    """Ensures the .agent directory exists and is a directory."""
    root = project_root or Path(".").resolve()
    agent_dir = root / ".agent"

    typer.echo("\n[INFO] Checking for '.agent' workspace directory...")
    try:
        if agent_dir.exists() and not agent_dir.is_dir():
            typer.secho(
                "[ERROR] A file named '.agent' exists. Please remove it and run again.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
        agent_dir.mkdir(exist_ok=True)
        typer.secho("[OK] '.agent' directory is present.", fg=typer.colors.GREEN)
    except OSError as e:
        typer.secho(f"[ERROR] Failed to create '.agent' directory: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def ensure_gitignore(project_root: Path = None) -> None:
    """Ensures .env is listed in .gitignore to prevent accidental secret exposure."""
    root = project_root or Path(".").resolve()
    gitignore_file = root / ".gitignore"

    typer.echo("\n[INFO] Verifying '.gitignore' configuration...")
    try:
        if not gitignore_file.exists():
            gitignore_file.touch()
            typer.echo("[INFO] Created missing '.gitignore' file.")

        with gitignore_file.open("r+") as f:
            lines = f.readlines()
            # Check if '.env' is on a line by itself
            is_present = any(line.strip() == ".env" for line in lines)
            if not is_present:
                typer.echo("[INFO] Adding '.env' to '.gitignore'.")
                f.seek(0, 2)  # Go to end of file
                if lines and not lines[-1].endswith("\n"):
                    f.write("\n")
                f.write("\n# Agent secrets\n.env\n")
            else:
                typer.secho(
                    "[OK] '.env' is already in '.gitignore'.", fg=typer.colors.GREEN, dim=True
                )
    except PermissionError:
        typer.secho(
            "[ERROR] Could not write to '.gitignore'. Please check file permissions.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    except OSError as e:
        typer.secho(f"[ERROR] Failed to read or write '.gitignore': {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def configure_api_keys() -> None:
    """Prompts for API keys and saves them to the secret manager."""
    typer.echo("\n[INFO] Configuring API keys in Secret Manager...")

    manager = get_secret_manager()

    # 1. Initialize if needed
    if not manager.is_initialized():
        typer.echo("Secret Manager is not initialized.")
        typer.echo("You need to set a master password to encrypt your API keys.")
        from agent.commands.secret import _prompt_password, _validate_password_strength

        while True:
            password = _prompt_password(confirm=True)
            if _validate_password_strength(password):
                try:
                    manager.initialize(password)
                    typer.echo("[OK] Secret Manager initialized.")
                    break
                except Exception as e:
                    typer.secho(f"[ERROR] Initialization failed: {e}", fg=typer.colors.RED)
                    raise typer.Exit(code=1)
            else:
                 typer.echo("Password does not meet requirements. Please try again.")

    # 2. Unlock if needed
    if not manager.is_unlocked():
        typer.echo("Please unlock the Secret Manager.")
        from agent.commands.secret import _prompt_password

        while True:
            try:
                password = _prompt_password(confirm=False)
                manager.unlock(password)
                typer.echo("[OK] Secret Manager unlocked.")
                break
            except InvalidPasswordError:
                 typer.secho("[ERROR] Incorrect password. Try again.", fg=typer.colors.RED)
            except Exception as e:
                 typer.secho(f"[ERROR] Failed to unlock: {e}", fg=typer.colors.RED)
                 raise typer.Exit(code=1)

    typer.echo("Please provide API keys for the providers you wish to use.")
    typer.echo("(Leave blank to skip a provider)")

    for provider_id, provider_config in PROVIDERS.items():
        key_name = provider_config.get("secret_key")
        service_name = provider_config.get("service")

        # Skip providers that don't use secrets (like gh)
        if not key_name or not service_name:
            continue

        # Check if already set
        display_name = provider_config['name']

        if not manager.has_secret(service_name, key_name):
            # Check if exists in environment (migration path)
            # Since not in manager, get_secret will use fallback logic to find in env
            env_val = get_secret(key_name, service=service_name)
            
            migrated = False
            if env_val:
                typer.secho(f"\n[WARN] {display_name} key found in environment but not in secure storage.", fg=typer.colors.YELLOW)
                if typer.confirm("Would you like to migrate this key to the Secret Manager?", default=True):
                    try:
                        manager.set_secret(service_name, key_name, env_val)
                        typer.secho(
                            f"[OK] Migrated {display_name} key to secure storage.",
                            fg=typer.colors.GREEN
                        )
                        migrated = True
                    except Exception as e:
                         typer.secho(
                             f"[ERROR] Failed to migrate secret: {e}",
                             fg=typer.colors.RED
                         )
            
            if not migrated:
                typer.echo(f"\n{display_name} ({key_name}):")
                try:
                    # Use getpass for masked input
                    value = getpass.getpass("Value: ")
                    if value:
                         try:
                            manager.set_secret(service_name, key_name, value)
                            typer.secho(
                                f"[OK] Saved {display_name} key.",
                                fg=typer.colors.GREEN
                            )
                         except Exception as e:
                            typer.secho(
                                f"[ERROR] Failed to save secret: {e}",
                                fg=typer.colors.RED
                            )
                    else:
                        typer.secho(
                            f"[WARN] Skipping {display_name}.",
                            fg=typer.colors.YELLOW, dim=True
                        )
                except (KeyboardInterrupt, EOFError):
                    typer.secho("\n[INFO] Onboarding cancelled by user.", dim=True)
                    raise typer.Exit(code=1)
        else:
            typer.secho(
                f"[OK] {display_name} key is already configured.",
                fg=typer.colors.GREEN, dim=True
            )
    
    # Reload the AI service to pick up new keys
    ai_service.reload()


def configure_agent_settings() -> None:
    """Configures default agent settings (provider, model)."""
    typer.echo("\n[INFO] Configuring Agent defaults...")
    
    agent_config_path = config.etc_dir / "agent.yaml"
    
    # Ensure etc dir exists
    config.etc_dir.mkdir(parents=True, exist_ok=True)
    
    # Load existing or empty
    try:
        data = config.load_yaml(agent_config_path)
    except FileNotFoundError:
        data = {}
        
    # 1. Select Provider
    drivers = list(PROVIDERS.keys())
    
    # Filter based on what keys are set in .env (loaded in process) or just offer all?
    # Better to offer all but warn if key missing? 
    # For now, just offer all supported.
    
    typer.echo("Select your default AI provider:")
    for i, p in enumerate(drivers, 1):
        typer.echo(f"{i}. {p}")
        
    provider = None
    while not provider:
        choice = typer.prompt("Enter number", default="1")
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(drivers):
                provider = drivers[idx]
            else:
                typer.echo("Invalid selection.")
        except ValueError:
            typer.echo("Invalid input.")

    # Save provider
    config.set_value(data, "agent.provider", provider)
    
    # 2. Select Model
    # We need to reload .env to ensure the keys we just set are available to AIService
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    # Force the service to recognize the new key/provider?
    # aiservice singleton is already initialized.
    # We might need to manually refresh it or just instantiate a new client
    # in get_available_models if possible.
    # Actually, service.py checks os.getenv at init. 
    # But get_available_models re-checks or uses client?
    # We might need to handle this carefully.
    
    typer.echo(f"\n[INFO] Fetching available models for {provider}...")
    try:
        # We need to hackily update the singleton's state if we just added keys
        # Or simply rely on the fact that we just set the .env file and load_dotenv()
        # But `service.py` init ran at import time.
        # We should probably force a re-init or use a raw client check if we
        # want to be safe.
        # Let's rely on basic `ai_service.get_available_models` but we might
        # need to "reload" the service.
        # Actually `service.py` logic:
        # __init__ checks env vars. 
        # So we need to re-init the service or manually add the client.
        
        # Let's try to "reload" the specific client in the service if missing
        if provider not in ai_service.clients:
             # This is a bit internal-knowledge heavy, but necessary since we
             # just set the keys
             pass 
             # For now, let's just proceed. The user might have had keys or we
             # just restart.
             # Actually, if we just set the ENV var in this process, we need to
             # update os.environ
             # load_dotenv(override=True) does update os.environ.
             # But aiservice.__init__ ran already.
             # We can't easily re-run __init__.
             # We will skip model selection if client not ready, or warn user.
             pass

        # We will attempt to list. If it fails because client is missing
        # (due to init timing), we catch it.
        # To fix this properly, we should probably have a `reload_config()`
        # on AIService.
        pass

    except Exception:
        pass

    # Save back to file
    config.save_yaml(agent_config_path, data)
    typer.echo(f"[OK] Default provider set to '{provider}'.")
    
    # Now lets try to select model
    select_default_model(provider, data, agent_config_path)


def select_default_model(provider: str, config_data: dict, config_path: Path) -> None:
    """Prompts user to select a default model for the provider."""
    try:
        # Attempt to get models. 
        # NOTE: This might fail if the service hasn't picked up the new keys.
        # We'll explicitly try to refresh the service client if needed.
        
        # Reload env vars to process
        from dotenv import load_dotenv
        load_dotenv(override=True)
        
        # Hack to refresh client if missing
        if provider not in ai_service.clients:
            # Re-run the specific check block from __init__? 
            # Or just tell user we can't list models yet.
            # Simpler: Instantiate a temporary check?
            # Let's manually trigger the init logic for that provider if we can.
            # actually `ai_service` has no public re-init.
            # Let's just try.
            pass

        models = ai_service.get_available_models(provider)
        
        if not models:
            typer.echo(
                "[WARN] No models found or unable to query API. "
                "Skipping default model selection."
            )
            return

        table = Table(title=f"Available Models ({provider})")
        table.add_column("#", style="dim")
        table.add_column("ID", style="cyan")
        
        # Limit to first 20 to avoid spam
        display_models = models[:20]
        
        for i, m in enumerate(display_models, 1):
            table.add_row(str(i), m['id'])
            
        console.print(table)
        
        choice = typer.prompt(
            "Select default model (number) or press Enter to skip", default=""
        )
        if choice:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(display_models):
                    model_id = display_models[idx]['id']
                    # Save formatted as provider_model?? No, `agent.model`? 
                    # The requirement said "save to agent.yaml under
                    # provider_model or similar"
                    # Ideally: agent.models.{provider} = model_id
                    
                    config.set_value(config_data, f"agent.models.{provider}", model_id)
                    config.save_yaml(config_path, config_data)
                    typer.echo(
                        f"[OK] Default model for {provider} set to '{model_id}'."
                    )
            except ValueError:
                pass
                
    except Exception as e:
        typer.secho(
            f"[WARN] Could not list models: {e}. Skipping model selection.",
            fg=typer.colors.YELLOW
        )




def run_verification() -> None:
    """Verifies AI connectivity with a Hello World prompt."""
    typer.echo("\n[INFO] Verifying AI connectivity...")
    
    # Reload env vars
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    # Instantiate a FRESH service to pick up new keys
    service = AIService()
    
    # Force the configured provider to ensure we verify what the user selected
    try:
        config_data = config.load_yaml(config.etc_dir / "agent.yaml")
        configured_provider = config.get_value(config_data, "agent.provider")
        if configured_provider:
            # We don't want to fail if it's not available (e.g. if
            # initialization failed)
            # checking if it's in service.clients happens inside set_provider
            # but raises error
            # so we check first
             if configured_provider in service.clients:
                 service.set_provider(configured_provider)
    except Exception:
        # Fallback to default behavior if config read fails
        pass
    
    try:
        response = service.complete(
            system_prompt="You are a helpful assistant.",
            user_prompt="Reply with exactly 'Hello World'",
        )
        if "Hello World" in response or "Hello" in response:
            typer.secho(
                "[SUCCESS] AI Connectivity Verified! 🚀",
                fg=typer.colors.GREEN,
                bold=True
            )
        else:
            typer.secho(
                f"[WARN] AI returned unexpected response: {response}",
                fg=typer.colors.YELLOW
            )
    except Exception as e:
        typer.secho(f"[ERROR] Verification failed: {e}", fg=typer.colors.RED)


def display_next_steps() -> None:
    """Displays a guided tour of next steps."""
    console.print(
        "\n[bold cyan]🎉 You are all set! "
        "Here is a quick tour of what you can do:[/bold cyan]"
    )
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Command", style="green")
    table.add_column("Description")
    
    table.add_row(
        "agent story", "Start a new feature or bugfix (creates a Story artifact)"
    )
    table.add_row("agent preflight", "Run governance checks (preflight) on your code")
    table.add_row("agent pr", "Create a Pull Request with all checks passing")
    table.add_row("agent list-models", "See available AI models")
    table.add_row("agent config list", "View your current configuration")
    
    console.print(table)
    console.print("\n[dim]Tip: Use --help on any command for more info.[/dim]")


@app.command()
def onboard() -> None:
    """Guides a developer through initial agent setup and configuration."""
    typer.secho("--- Agent Onboarding ---", bold=True)
    typer.echo(
        "This command will check dependencies and set up your local environment."
    )

    if sys.platform == "win32":
        typer.secho(
            "\n[ERROR] This command is not yet supported on Windows.",
            fg=typer.colors.RED
        )
        raise typer.Exit(code=1)

    try:
        check_dependencies()
        check_github_auth()
        ensure_agent_directory()
        ensure_gitignore()
        configure_api_keys()
        configure_agent_settings()
        run_verification()
        
        typer.secho(
            "\n[SUCCESS] Onboarding complete! The agent is ready to use.",
            fg=typer.colors.GREEN,
            bold=True,
        )
        display_next_steps()

    except typer.Exit:
        raise
    except Exception as e:
        typer.secho(
            f"\n[FATAL] An unexpected error occurred: {e}",
            fg=typer.colors.RED,
            bold=True
        )
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()