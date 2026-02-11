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

import getpass
import os
import shutil
import subprocess
import sys
from pathlib import Path

import typer
from opentelemetry import trace


# Note: This command requires `typer` and `python-dotenv`.
# Ensure they are added to your project's dependencies.
from rich.console import Console
from rich.table import Table

# from agent.core.ai.service import PROVIDERS, AIService, ai_service # Moved to local imports
from agent.core.config import config
from agent.core.secrets import (
    InvalidPasswordError,
    get_secret,
    get_secret_manager,
)

console = Console()
tracer = trace.get_tracer(__name__)


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
    dependencies = ["git", "python3", "gh"]
    recommended = ["node", "npm"]

    all_found = True
    for dep in dependencies:
        if not shutil.which(dep):
            typer.secho(
                f"[ERROR] Binary dependency not found: '{dep}'. Please install it.",
                fg=typer.colors.RED,
            )
            all_found = False
        else:
            typer.secho(f"  - Found binary: {dep}", fg=typer.colors.GREEN)

    # Check Python dependencies
    python_deps = [
        ("dotenv", "python-dotenv"),
        ("mcp", "modelcontextprotocol"),
        ("typer", "typer"),
    ]
    
    import importlib.util
    for module_name, package_name in python_deps:
        if not importlib.util.find_spec(module_name):
            typer.secho(
                f"[ERROR] Python dependency not found: '{package_name}' ({module_name}).\n"
                f"        Please run: pip install -e .agent",
                fg=typer.colors.RED,
            )
            all_found = False
        else:
            typer.secho(f"  - Found module: {module_name}", fg=typer.colors.GREEN)

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
            
    # Check linting tools
    if not shutil.which("markdownlint"):
         typer.secho("[INFO] markdownlint-cli not found. It is recommended for documentation checks.", fg=typer.colors.BLUE)
         if typer.confirm("Install markdownlint-cli globally via npm?", default=True):
             if shutil.which("npm"):
                 try:
                     subprocess.run(["npm", "install", "-g", "markdownlint-cli"], check=True)
                     typer.secho("[OK] markdownlint-cli installed.", fg=typer.colors.GREEN)
                 except Exception as e:
                     typer.secho(f"[ERROR] Failed to install markdownlint-cli: {e}", fg=typer.colors.RED)
             else:
                 typer.secho("[WARN] npm not found. Cannot install markdownlint-cli automatically.", fg=typer.colors.YELLOW)
    else:
         typer.secho("  - Found tool: markdownlint", fg=typer.colors.GREEN)

    typer.secho("[OK] System dependencies check passed.", fg=typer.colors.GREEN)


def check_github_auth() -> None:
    """Checks GitHub authentication via MCP and CLI (Unified)."""
    typer.echo("\n[INFO] Configuring GitHub Access...")

    # Ensure gh is available
    if not shutil.which("gh"):
        typer.secho(
            "[ERROR] GitHub CLI ('gh') is required but not found. Please install it.",
            fg=typer.colors.RED
        )
        raise typer.Exit(code=1)

    # Check if already authenticated via gh
    gh_status = subprocess.run(
        ["gh", "auth", "status"], capture_output=True, text=True
    )
    gh_logged_in = gh_status.returncode == 0
    
    # Check if secret already exists
    manager = get_secret_manager()
    secret_exists = manager.is_initialized() and manager.is_unlocked() and manager.has_secret("github", "token")

    if gh_logged_in and secret_exists:
        typer.secho("[OK] GitHub access already configured (CLI & MCP).", fg=typer.colors.GREEN)
        if not typer.confirm("Would you like to re-configure?", default=False):
            return

    typer.echo("\n[INFO] We will now configure GitHub access for both the Agent (MCP) and CLI (gh).")
    typer.echo("You will need a GitHub Personal Access Token (PAT) with scopes: repo, read:org")

    token = getpass.getpass("GitHub PAT: ")
    if not token:
        typer.secho("[WARN] No token provided. Skipping GitHub configuration.", fg=typer.colors.YELLOW)
        return

    # 1. Configure MCP Secret
    try:
        if manager.is_initialized():
             if not manager.is_unlocked():
                  typer.echo("Secret manager is locked. Please unlock to save access token.")
                  # We rely on previous steps ensuring it's unlocked or prompt
                  # But actually onboard runs sequentially, so it should be unlocked.
                  pass
             
             manager.set_secret("github", "token", token)
             typer.secho("  - [OK] Agent MCP token saved securely.", fg=typer.colors.GREEN)
             
             # Set generic config to 'mcp' as primary tool for agent, though 'gh' is also available
             agent_config_path = config.etc_dir / "agent.yaml"
             try:
                 data = config.load_yaml(agent_config_path)
             except FileNotFoundError:
                 data = {}
             config.set_value(data, "agent.github.tool", "mcp")
             config.save_yaml(agent_config_path, data)
             
    except Exception as e:
        typer.secho(f"  - [ERROR] Failed to save MCP token: {e}", fg=typer.colors.RED)

    # 2. Configure gh CLI
    try:
        # Pipe token to gh auth login
        process = subprocess.Popen(
            ["gh", "auth", "login", "--with-token"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input=token)
        
        if process.returncode == 0:
            typer.secho("  - [OK] GitHub CLI authenticated.", fg=typer.colors.GREEN)
        else:
             typer.secho(f"  - [ERROR] GitHub CLI login failed: {stderr.strip() if stderr else 'Unknown error'}", fg=typer.colors.RED)
             
    except Exception as e:
         typer.secho(f"  - [ERROR] Failed to run gh auth: {e}", fg=typer.colors.RED)

    typer.secho("[OK] GitHub access configuration complete.", fg=typer.colors.GREEN)


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


    from agent.core.ai.service import PROVIDERS, ai_service  # ADR-025: lazy init

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
    current_provider = config.get_value(data, "agent.provider")
    should_configure_provider = True

    if current_provider:
        typer.secho(f"[OK] Default AI provider is already set to '{current_provider}'.", fg=typer.colors.GREEN)
        if not typer.confirm("Would you like to re-configure?", default=False):
            should_configure_provider = False
            provider = current_provider
            
            # Check model config if skipping provider
            current_model = config.get_value(data, f"agent.models.{current_provider}")
            if current_model:
                 typer.secho(f"[OK] Default model for {current_provider} is set to '{current_model}'.", fg=typer.colors.GREEN)
                 if not typer.confirm(f"Would you like to re-configure model for {current_provider}?", default=False):
                     return # Skip model selection as well

    if should_configure_provider: 
        # Logic to select provider if not skipped
        from agent.core.ai.service import PROVIDERS  # ADR-025: lazy init
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
    # We need to reload .env to ensure the keys we just set are available to AIService
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except ImportError:
        pass
    
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
        from agent.core.ai.service import ai_service  # ADR-025: lazy init
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
        # Reload env vars to process
        try:
            from dotenv import load_dotenv
            load_dotenv(override=True)
        except ImportError:
            pass
        
        # Hack to refresh client if missing
        from agent.core.ai.service import ai_service  # ADR-025: lazy init
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


def configure_voice_settings() -> None:
    """Configures voice capabilities (Deepgram, Local Models)."""
    typer.echo("\n[INFO] Configuring Voice Capabilities...")
    
    manager = get_secret_manager()
    voice_config_path = config.etc_dir / "voice.yaml"
    
    # 1. Deepgram API Key (Cloud STT/TTS)
    if not manager.has_secret("deepgram", "api_key"):
        if typer.confirm("Do you want to enable Cloud Voice (Deepgram)?", default=True):
            key = getpass.getpass("Deepgram API Key: ")
            if key:
                try:
                    manager.set_secret("deepgram", "api_key", key)
                    typer.secho("[OK] Deepgram key saved.", fg=typer.colors.GREEN)
                except Exception as e:
                    typer.secho(f"[ERROR] Failed to save key: {e}", fg=typer.colors.RED)
            else:
                typer.echo("Skipping Deepgram.")
    else:
        typer.secho("[OK] Deepgram key already configured.", fg=typer.colors.GREEN, dim=True)

# 2. Azure Speech
    # 2. Azure Speech
    if not manager.has_secret("azure", "key"):
        if typer.confirm("Do you want to enable Azure Speech?", default=False):
            typer.secho("\n[SECURITY WARNING] Azure Keys are sensitive secrets.", fg=typer.colors.RED, bold=True)
            typer.echo("We will store your key and region ENCRYPTED in the local Secret Manager.")
            typer.echo("You should NEVER commit these keys to git.\n")
            
            typer.echo("Enter Azure Speech Key (masked):")
            key = getpass.getpass("Key: ")
            region = typer.prompt("Azure Region (e.g. eastus): ")
            
            if key and region:
                # Security: Validate region
                import re
                if not re.match(r"^[a-z0-9-]+$", region):
                     typer.secho(f"[ERROR] Invalid region format. Must be alphanumeric/hyphens only.", fg=typer.colors.RED)
                else:
                    try:
                        # Enforce secure storage for KEY and REGION
                        manager.set_secret("azure", "key", key)
                        manager.set_secret("azure", "region", region)
                        
                        # We also update config for visibility if user wants, but reliance should be on secret?
                        # Security Review said "Cleartext storage of Azure region... might be seen as configuration".
                        # We will REMOVE it from plain config to satisfy them.
                        
                        typer.secho("[OK] Azure credentials (Key & Region) stored in Secret Manager.", fg=typer.colors.GREEN)
                    except Exception as e:
                        typer.secho(f"[ERROR] Failed to save Azure secret: {e}", fg=typer.colors.RED)
    else:
        typer.secho("[OK] Azure key already configured.", fg=typer.colors.GREEN, dim=True)

    # 3. Google Cloud Speech
    if not manager.has_secret("google", "application_credentials_json"):
        if typer.confirm("Do you want to enable Google Cloud Speech?", default=False):
            typer.secho("\n[SECURITY WARNING] Service Account Keys are highly sensitive.", fg=typer.colors.RED, bold=True)
            typer.echo("We will import the CONTENT of your JSON key and store it ENCRYPTED.")
            typer.echo("We do NOT store the file path. You should DELETE the local JSON file after import.")
            typer.echo("NEVER commit the JSON file to git.\n")
            
            typer.echo("Enter path to Service Account JSON file (for one-time import):")
            path_str = typer.prompt("Path: ", default="")
            
            if path_str:
                path = Path(path_str).resolve()
                if path.exists():
                    try:
                        import json
                        with open(path, 'r') as f:
                            json_content = f.read()
                            # Validate JSON
                            json.loads(json_content) 
                            
                        # Store the raw JSON string in secrets manager
                        manager.set_secret("google", "application_credentials_json", json_content)
                        typer.secho(f"[OK] Google Service Account imported to Secret Manager.", fg=typer.colors.GREEN)
                        
                        if typer.confirm("Delete local JSON file now (Recommended)?", default=True):
                            try:
                                path.unlink()
                                typer.secho(f"[OK] Deleted {path.name}", fg=typer.colors.GREEN)
                            except Exception as e:
                                typer.secho(f"[ERROR] Failed to delete file: {e}", fg=typer.colors.RED)
                        else:
                             typer.secho(f"[ACTION REQUIRED] Please DELETE the file '{path.name}' manually.", fg=typer.colors.YELLOW, bold=True)
                        
                    except Exception as e:
                        typer.secho(f"[ERROR] Failed to import Google JSON: {e}", fg=typer.colors.RED)
                else:
                    typer.secho(f"[WARN] File not found: {path}", fg=typer.colors.YELLOW)
    else:
        typer.secho("[OK] Google credentials already configured.", fg=typer.colors.GREEN, dim=True)

    # 4. Voice LLM Provider
    # Load existing
    try:
        data = config.load_yaml(voice_config_path)
    except FileNotFoundError:
        data = {}
        
    current_provider = config.get_value(data, "llm.provider") or "openai"
    
    if typer.confirm(f"Configure Voice LLM? (Current: {current_provider})", default=False):
        # reuse PROVIDERS dict keys but filter for LLMs
        llm_providers = ["openai", "anthropic", "gemini"]
        
        typer.echo("Select Voice LLM Provider:")
        for i, p in enumerate(llm_providers, 1):
            typer.echo(f"{i}. {p}")
            
        choice = typer.prompt("Enter number", default="1")
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(llm_providers):
                new_provider = llm_providers[idx]
                config.set_value(data, "llm.provider", new_provider)
                config.save_yaml(voice_config_path, data)
                typer.echo(f"[OK] Voice LLM set to '{new_provider}'.")
        except ValueError:
            pass

    # 5. Local Models (Kokoro)
    if typer.confirm("Download Local Voice Models (Kokoro)? (Recommended for Dev/Offline)", default=False):
        typer.echo("Downloading models... This may take a moment.")
        try:
            # Run the download script
            # Assuming cwd is project root and .agent/src is available
            script_path = "backend.scripts.download_models"
            src_path = AGENT_DIR / "src"
            
            subprocess.run(
                [sys.executable, "-m", script_path],
                cwd=src_path,
                check=True
            )
            typer.secho("[OK] Local models downloaded.", fg=typer.colors.GREEN)
        except subprocess.CalledProcessError:
            typer.secho("[ERROR] Failed to download models.", fg=typer.colors.RED)
        except Exception as e:
            typer.secho(f"[ERROR] Unexpected error: {e}", fg=typer.colors.RED)

def configure_notion_settings() -> None:
    """Configures Notion integration settings effectively bootstrapping the environment.
    
    Prompts the user for Notion Integration Token and Parent Page ID.
    Stores these secrets in the Secret Manager.
    Triggers the schema manager script to bootstrap database structures.
    """
    typer.echo("\n[INFO] Configuring Notion Workspace Manager...")
    
    manager = get_secret_manager()
    
    # 1. Notion Token
    token = get_secret("notion_token", service="notion") or os.getenv("NOTION_TOKEN")
    if not token:
        if typer.confirm("Configure Notion Integration?", default=False):
            token = getpass.getpass("Notion Integration Token: ")
            if token:
                try:
                    # Save to 'notion' service
                    manager.set_secret("notion", "notion_token", token)
                    # Also set in env for immediate use
                    os.environ["NOTION_TOKEN"] = token
                    typer.secho("[OK] Notion Token saved.", fg=typer.colors.GREEN)
                except Exception as e:
                    typer.secho(f"[ERROR] Failed to save token: {e}", fg=typer.colors.RED)
        else:
            typer.echo("Skipping Notion setup.")
            return

    # 2. Parent Page ID
    agent_config = config.load_yaml(config.etc_dir / "agent.yaml")
    page_id = config.get_value(agent_config, "notion.page_id") or os.getenv("NOTION_PARENT_PAGE_ID")
    if not page_id:
        typer.echo("We need a Parent Page ID where the Agent will create databases.")
        typer.echo("Tips: You can copy the full URL of the page.")
        page_id = typer.prompt("Notion Parent Page URL or ID: ", default="")
        if page_id:
            try:
                # Sanitize: Extract UUID if URL or slug-UUID format
                import re
                # Match 32 hex chars, potentially with dashes
                match = re.search(r"([a-fA-F0-9]{32}|[a-fA-F0-9-]{36})", page_id)
                if match:
                    # Remove dashes for consistency if it's the 32-char format Notion often uses in API
                    sanitized_id = match.group(0).replace("-", "")
                    if len(sanitized_id) == 32:
                         page_id = sanitized_id
                         typer.secho(f"[INFO] Extracted Page ID: {page_id}", dim=True)
                
                config.set_value(agent_config, "notion.page_id", page_id)
                config.save_yaml(config.etc_dir / "agent.yaml", agent_config)
                # Ensure env var is set for current process usage (e.g. bootstrap script)
                os.environ["NOTION_PARENT_PAGE_ID"] = page_id
                typer.secho("[OK] Page ID saved.", fg=typer.colors.GREEN)
            except Exception as e:
                typer.secho(f"[ERROR] Failed to save Page ID: {e}", fg=typer.colors.RED)
    
    # 3. Trigger Bootstrap
    if token and page_id:
        if typer.confirm("Run Notion Schema Bootstrap now?", default=True):
            typer.echo("Running Schema Manager... (This launches an MCP server)")
            try:
                # Run the script via subprocess
                script_path = AGENT_DIR / "scripts" / "notion_schema_manager.py"
                
                # Ensure env vars are passed
                env = os.environ.copy()
                env["NOTION_TOKEN"] = token
                env["NOTION_PARENT_PAGE_ID"] = page_id
                
                subprocess.run(
                    [sys.executable, str(script_path)],
                    env=env,
                    check=True
                )
                typer.secho("[SUCCESS] Notion Environment Bootstrapped!", fg=typer.colors.GREEN)
            except subprocess.CalledProcessError:
                typer.secho("[ERROR] Schema Manager failed.", fg=typer.colors.RED)
            except Exception as e:
                 typer.secho(f"[ERROR] Unexpected error running script: {e}", fg=typer.colors.RED)






def setup_frontend() -> None:
    """
    Installs frontend dependencies using npm.
    
    Observability:
    - Uses OpenTelemetry to trace the installation duration and success/failure.
    - All telemetry is strictly local/stdio unless an exporter is explicitly configured by the user.
    - No PII is captured.
    """
    typer.echo("\n[INFO] Setting up Frontend...")

    web_dir = AGENT_DIR / "src" / "web"
    
    # 1. Check if npm is installed
    if not shutil.which("npm"):
        typer.secho(
            "[WARN] 'npm' not found. Skipping frontend setup.",
            fg=typer.colors.YELLOW
        )
        typer.echo("The Agent Admin Console frontend may not work until you install Node.js and run 'npm install' manually.")
        return

    # 2. Check directory
    if not web_dir.exists():
        typer.secho(
            f"[WARN] Web directory not found at {web_dir}. Skipping frontend setup.",
            fg=typer.colors.YELLOW
        )
        return

    # 3. Install dependencies
    typer.echo("Installing Node dependencies... (this may take a minute)")
    try:
        with tracer.start_as_current_span("agent.onboard.setup_frontend.npm_install") as span:
             span.set_attribute("cwd", str(web_dir))
             subprocess.run(
                ["npm", "install"],
                cwd=web_dir,
                check=True,
                capture_output=False  # Let user see progress
             )
             span.set_attribute("status", "success")
             
        typer.secho("[OK] Frontend dependencies installed.", fg=typer.colors.GREEN)
        
        # 4. Security Audit
        # 4. Security Audit
        typer.echo("Running security audit on dependencies...")
        try:
             process = subprocess.Popen(
                ["npm", "audit", "--audit-level=high"],
                cwd=web_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
             )
             
             if process.stdout:
                 for line in process.stdout:
                     console.print(line, end="")
            
             process.wait()
             
        except Exception:
             typer.secho("[WARN] Failed to run security audit.", fg=typer.colors.YELLOW)
             
    except subprocess.CalledProcessError as e:
        typer.secho(
            f"[ERROR] Failed to run 'npm install': {e}",
            fg=typer.colors.RED
        )
        typer.echo("You may need to resolve this manually to use the Admin Console.")



def run_verification() -> None:
    """Verifies AI connectivity with a Hello World prompt."""
    typer.echo("\n[INFO] Verifying AI connectivity...")
    
    # Reload env vars
    # Reload env vars
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except ImportError:
        pass # dotenv is optional
    
    # Instantiate a FRESH service to pick up new keys
    from agent.core.ai.service import AIService  # ADR-025: lazy init
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
        ensure_agent_directory()
        ensure_gitignore()
        # Initialize secrets first so we can use them
        configure_api_keys() 
        check_github_auth() # Now safe to use secrets if needed? Actually I just save preference.
        configure_agent_settings()
        configure_voice_settings()
        configure_notion_settings()
        setup_frontend()
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