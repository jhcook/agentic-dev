import getpass
import os
import shutil
import stat
import sys
from pathlib import Path
from typing import Dict, List

import typer
# Note: This command requires `typer` and `python-dotenv`.
# Ensure they are added to your project's dependencies.
from dotenv import dotenv_values, set_key

# Define the API keys required for the agent to function.
REQUIRED_KEYS: List[str] = ["OPENAI_API_KEY"]

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
    dependencies = ["git"]
    all_found = True
    for dep in dependencies:
        if not shutil.which(dep):
            typer.secho(
                f"[ERROR] Dependency not found: '{dep}'. Please install it and run onboard again.",
                fg=typer.colors.RED,
            )
            all_found = False
    if not all_found:
        raise typer.Exit(code=1)
    typer.secho("[OK] All system dependencies are present.", fg=typer.colors.GREEN)


def ensure_agent_directory(project_root: Path = None) -> None:
    """Ensures the .agent directory exists and is a directory."""
    root = project_root or Path(".").resolve()
    agent_dir = root / ".agent"
    
    typer.echo("[INFO] Checking for '.agent' workspace directory...")
    try:
        if agent_dir.exists() and not agent_dir.is_dir():
            typer.secho(
                f"[ERROR] A file named '.agent' exists. Please remove it and run again.",
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
    
    typer.echo("[INFO] Verifying '.gitignore' configuration...")
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
            f"[ERROR] Could not write to '.gitignore'. Please check file permissions.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    except OSError as e:
        typer.secho(f"[ERROR] Failed to read or write '.gitignore': {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def configure_api_keys(project_root: Path = None) -> None:
    """Interactively prompts for and saves required API keys in a secure .env file."""
    root = project_root or Path(".").resolve()
    env_file = root / ".env"
    
    typer.echo("[INFO] Configuring API keys in '.env' file...")

    if not env_file.exists():
        env_file.touch()
        typer.echo("[INFO] Created '.env' file for API keys.")

    try:
        # Set permissions to 600 (owner read/write) as per @Security review
        os.chmod(env_file, 0o600)
    except OSError as e:
        typer.secho(
            f"[WARN] Could not set permissions on '.env': {e}. Please set them to 600 manually.",
            fg=typer.colors.YELLOW,
        )

    existing_config: Dict[str, str] = {
        k: v for k, v in dotenv_values(env_file).items() if v is not None
    }
    keys_to_set: Dict[str, str] = {}

    for key in REQUIRED_KEYS:
        if key not in existing_config or not existing_config[key]:
            typer.echo(f"\nPlease provide your {key}:")
            try:
                # Use getpass for masked input
                value = getpass.getpass("Value: ")
                if value:
                    keys_to_set[key] = value
                else:
                    typer.secho(
                        f"[WARN] No value provided for {key}. Skipping.", fg=typer.colors.YELLOW
                    )
            except (KeyboardInterrupt, EOFError):
                typer.secho("\n[INFO] Onboarding cancelled by user.", dim=True)
                raise typer.Exit(code=1)
        else:
            typer.secho(f"[OK] {key} is already configured.", fg=typer.colors.GREEN, dim=True)

    if not keys_to_set:
        typer.echo("[INFO] All required API keys are already configured.")
        return

    typer.echo("\n[INFO] Saving new API keys to '.env' file...")
    try:
        for key, value in keys_to_set.items():
            set_key(str(env_file), key, value)

        # Re-apply permissions after writing
        os.chmod(env_file, 0o600)
        typer.secho("[OK] Successfully saved configuration.", fg=typer.colors.GREEN)
    except (OSError, PermissionError) as e:
        typer.secho(
            f"[ERROR] Could not write to '.env' file: {e}. Please check permissions.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)


@app.command()
def onboard() -> None:
    """Guides a developer through initial agent setup and configuration."""
    typer.secho("--- Agent Onboarding ---", bold=True)
    typer.echo("This command will check dependencies and set up your local environment.")

    if sys.platform == "win32":
        typer.secho("\n[ERROR] This command is not yet supported on Windows.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    try:
        check_dependencies()
        ensure_agent_directory()
        ensure_gitignore()
        configure_api_keys()

        typer.secho(
            "\n[SUCCESS] Onboarding complete! The agent is ready to use.",
            fg=typer.colors.GREEN,
            bold=True,
        )
        typer.echo("You can now run the agent using its main commands.")

    except typer.Exit:
        raise
    except Exception as e:
        typer.secho(f"\n[FATAL] An unexpected error occurred: {e}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()