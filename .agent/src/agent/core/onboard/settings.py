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

"""Core Onboarding Steps Library.

This module contains the isolated, procedural logic for each onboarding
step required by the `agent onboard` workflow. By keeping these steps
separate from the Typer CLI facade, they can be tested independently and
invoked programmatically by bootstrap scripts.
"""

from pathlib import Path
from typing import Dict

from opentelemetry import trace
from agent.core.onboard.prompter import Prompter



# Note: This command requires `typer` and `python-dotenv`.
# Ensure they are added to your project's dependencies.

# from agent.core.ai.service import PROVIDERS, AIService, ai_service # Moved to local imports
from agent.core.config import config
from agent.core.secrets import (
    InvalidPasswordError,
    get_secret,
    get_secret_manager,
)
from agent.core.logger import get_logger

tracer = trace.get_tracer(__name__)
logger = get_logger(__name__)


# REQUIRED_KEYS removed, driven by PROVIDERS constant from service.py

# Define project paths relative to the current working directory.
# This assumes the command is run from the project root.
PROJECT_ROOT: Path = Path(".").resolve()
AGENT_DIR: Path = PROJECT_ROOT / ".agent"
ENV_FILE: Path = PROJECT_ROOT / ".env"
GITIGNORE_FILE: Path = PROJECT_ROOT / ".gitignore"

def configure_api_keys(prompter: Prompter) -> None:
    """Prompts for API keys and saves them to the secret manager."""
    logger.info("Configuring API keys", extra={"step": "configure_api_keys"})
    prompter.echo("\n[INFO] Configuring API keys in Secret Manager...")

    manager = get_secret_manager()

    # 1. Initialize if needed
    if not manager.is_initialized():
        prompter.echo("Secret Manager is not initialized.")
        prompter.echo("You need to set a master password to encrypt your API keys.")
        from agent.core.auth.utils import validate_password_strength

        while True:
            password = prompter.getpass("Master password: ")
            password_confirm = prompter.getpass("Confirm password: ")
            if password != password_confirm:
                prompter.secho("[ERROR] Passwords do not match.", color="red")
                continue

            is_valid, err_msg = validate_password_strength(password)
            if is_valid:
                try:
                    manager.initialize(password)
                    prompter.echo("[OK] Secret Manager initialized.")
                    break
                except Exception as e:
                    prompter.secho(f"[ERROR] Initialization failed: {e}", color="red")
                    prompter.exit(1)
            else:
                 prompter.echo(f"Password does not meet requirements: {err_msg}")

    # 2. Unlock if needed
    if not manager.is_unlocked():
        prompter.echo("Please unlock the Secret Manager.")

        while True:
            try:
                password = prompter.getpass("Master password: ")
                manager.unlock(password)
                prompter.echo("[OK] Secret Manager unlocked.")
                break
            except InvalidPasswordError:
                 prompter.secho("[ERROR] Incorrect password. Try again.", color="red")
            except Exception as e:
                 prompter.secho(f"[ERROR] Failed to unlock: {e}", color="red")
                 prompter.exit(1)

    prompter.echo("Please provide API keys for the providers you wish to use.")
    prompter.echo("(Leave blank to skip a provider)")


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
                prompter.secho(f"\n[WARN] {display_name} key found in environment but not in secure storage.", color="yellow")
                if prompter.confirm("Would you like to migrate this key to the Secret Manager?", default=True):
                    try:
                        manager.set_secret(service_name, key_name, env_val)  # no-preflight-check
                        prompter.secho(
                            f"[OK] Migrated {display_name} key to secure storage.",
                            color="green"
                        )
                        migrated = True
                    except Exception as e:
                         prompter.secho(
                             f"[ERROR] Failed to migrate secret: {e}",
                             color="red"
                         )
            
            if not migrated:
                if service_name == "vertex":
                    if prompter.confirm(f"\nDo you want to configure {display_name}?", default=False):
                        prompter.secho("\n[INFO] For setup instructions, see: docs/getting_started.md", dim=True)
                        prompter.echo(f"{display_name} (Google Cloud Project ID):")  # no-preflight-check
                        try:
                            value = prompter.prompt("Project ID")
                            if value:
                                try:
                                    manager.set_secret(service_name, key_name, value)  # no-preflight-check
                                    prompter.secho(f"[OK] Saved {display_name} project ID.", color="green")
                                except Exception as e:
                                    prompter.secho(f"[ERROR] Failed to save secret: {e}", color="red")
                            else:
                                prompter.secho(f"[WARN] Skipping {display_name} configuration.", color="yellow", dim=True)
                        except (KeyboardInterrupt, EOFError):
                            prompter.secho("\n[INFO] Onboarding cancelled by user.", dim=True)
                            prompter.exit(1)
                    else:
                        prompter.secho(f"[WARN] Skipping {display_name} configuration.", color="yellow", dim=True)
                else:
                    prompter.echo(f"\n{display_name} ({key_name}):")
                    try:
                        # Use getpass for masked input
                        value = prompter.getpass("Value: ")  # no-preflight-check
                        if value:
                             try:
                                manager.set_secret(service_name, key_name, value)  # no-preflight-check
                                prompter.secho(
                                    f"[OK] Saved {display_name} key.",
                                    color="green"
                                )
                             except Exception as e:
                                prompter.secho(
                                    f"[ERROR] Failed to save secret: {e}",
                                    color="red"
                                )
                        else:
                            prompter.secho(
                                f"[WARN] Skipping {display_name}.",
                                color="yellow", dim=True
                            )
                    except (KeyboardInterrupt, EOFError):
                        prompter.secho("\n[INFO] Onboarding cancelled by user.", dim=True)
                        prompter.exit(1)
        else:
            prompter.secho(
                f"[OK] {display_name} key is already configured.",
                color="green", dim=True
            )
    
    # Reload the AI service to pick up new keys
    ai_service.reload()


def configure_agent_settings(prompter: Prompter) -> None:
    """Configures default agent settings (provider, model)."""
    logger.info("Configuring Agent defaults", extra={"step": "configure_agent_settings"})
    prompter.echo("\n[INFO] Configuring Agent defaults...")
    
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
    should_configure_model = True

    if current_provider:
        prompter.secho(f"[OK] Default AI provider is already set to '{current_provider}'.", color="green")
        if not prompter.confirm("Would you like to re-configure?", default=False):
            should_configure_provider = False
            provider = current_provider
            
            # Check model config if skipping provider
            current_model = config.get_value(data, f"agent.models.{current_provider}")
            if current_model:
                 prompter.secho(f"[OK] Default model for {current_provider} is set to '{current_model}'.", color="green")
                 if not prompter.confirm(f"Would you like to re-configure model for {current_provider}?", default=False):
                     should_configure_model = False

    if should_configure_provider: 
        # Logic to select provider if not skipped
        from agent.core.ai.service import PROVIDERS  # ADR-025: lazy init
        drivers = list(PROVIDERS.keys())
        
        # Filter based on what keys are set in .env (loaded in process) or just offer all?
        # Better to offer all but warn if key missing? 
        # For now, just offer all supported.
        
        prompter.echo("Select your default AI provider:")
        for i, p in enumerate(drivers, 1):
            prompter.echo(f"{i}. {p}")
            
        provider = None
        while not provider:
            choice = prompter.prompt("Enter number", default="1")
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(drivers):
                    provider = drivers[idx]
                else:
                    prompter.echo("Invalid selection.")
            except ValueError:
                prompter.echo("Invalid input.")



        # Save provider
        config.set_value(data, "agent.provider", provider)
    
    # 2. Select Model
    if should_configure_model:
        # We need to reload .env to ensure the keys we just set are available to AIService
        try:
            from dotenv import load_dotenv
            load_dotenv(override=True)
        except ImportError:
            pass
        
        prompter.echo(f"\n[INFO] Fetching available models for {provider}...")
        try:
            from agent.core.ai.service import ai_service  # ADR-025: lazy init
            if provider not in ai_service.clients:
                 pass
        except Exception:
            pass

        # Save back to file
        config.save_yaml(agent_config_path, data)
        prompter.echo(f"[OK] Default provider set to '{provider}'.")
        
        # Now lets try to select model
        select_default_model(prompter, provider, data, agent_config_path)

    # 3. Select Panel Engine (INFRA-061)
    # Reload data after model selection may have saved
    try:
        data = config.load_yaml(agent_config_path)
    except FileNotFoundError:
        data = {}

    current_engine = config.get_value(data, "panel.engine")
    should_configure_engine = True

    if current_engine:
        prompter.secho(f"[OK] Panel engine is already set to '{current_engine}'.", color="green")
        if not prompter.confirm("Would you like to re-configure?", default=False):
            should_configure_engine = False

    if should_configure_engine:
        engines = [
            ("native", "Sequential panel (default)"),
            ("adk", "Multi-agent via Google ADK (requires google-adk)"),
        ]
        prompter.echo("\nSelect panel engine:")
        for i, (key, desc) in enumerate(engines, 1):
            prompter.echo(f"{i}. {key} — {desc}")

        choice = prompter.prompt("Enter number", default="1")
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(engines):
                selected_engine = engines[idx][0]
                config.set_value(data, "panel.engine", selected_engine)
                config.save_yaml(agent_config_path, data)
                prompter.secho(f"[OK] Panel engine set to '{selected_engine}'.", color="green")
            else:
                prompter.echo("Invalid selection. Keeping default.")
        except ValueError:
            prompter.echo("Invalid input. Keeping default.")


def select_default_model(prompter: Prompter, provider: str, config_data: Dict, config_path: Path) -> None:
    """Prompts user to select a default model for the provider."""
    logger.info(f"Selecting default model for {provider}", extra={"step": "select_default_model"})
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
            prompter.echo(
                "[WARN] No models found or unable to query API. "
                "Skipping default model selection."
            )
            return

        columns = ["#", "ID"]
        rows = []
        
        # Limit to first 20 to avoid spam
        display_models = models[:20]
        
        for i, m in enumerate(display_models, 1):
            rows.append([str(i), m['id']])
            
        prompter.print_table(f"Available Models ({provider})", columns, rows)
        
        choice = prompter.prompt(
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
                    prompter.echo(
                        f"[OK] Default model for {provider} set to '{model_id}'."
                    )
            except ValueError:
                pass
                
    except Exception as e:
        prompter.secho(
            f"[WARN] Could not list models: {e}. Skipping model selection.",
            color="yellow"
        )


