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

import os
import subprocess
import sys
from pathlib import Path

from opentelemetry import trace
from agent.core.onboard.prompter import Prompter



# Note: This command requires `typer` and `python-dotenv`.
# Ensure they are added to your project's dependencies.

# from agent.core.ai.service import PROVIDERS, AIService, ai_service # Moved to local imports
from agent.core.config import config
from agent.core.secrets import (
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

def configure_voice_settings(prompter: Prompter) -> None:
    """Configures voice capabilities (Deepgram, Local Models)."""
    logger.info("Configuring voice settings", extra={"step": "configure_voice_settings"})
    prompter.echo("\n[INFO] Configuring Voice Capabilities...")
    
    manager = get_secret_manager()
    voice_config_path = config.etc_dir / "voice.yaml"
    
    # 1. Deepgram API Key (Cloud STT/TTS)
    if not manager.has_secret("deepgram", "api_key"):
        if prompter.confirm("Do you want to enable Cloud Voice (Deepgram)?", default=True):
            key = prompter.getpass("Deepgram API Key: ")  # no-preflight-check
            if key:
                try:
                    manager.set_secret("deepgram", "api_key", key)  # no-preflight-check
                    prompter.secho("[OK] Deepgram key saved.", color="green")
                except Exception as e:
                    prompter.secho(f"[ERROR] Failed to save key: {e}", color="red")
            else:
                prompter.echo("Skipping Deepgram.")
    else:
        prompter.secho("[OK] Deepgram key already configured.", color="green", dim=True)

# 2. Azure Speech
    # 2. Azure Speech
    if not manager.has_secret("azure", "key"):
        if prompter.confirm("Do you want to enable Azure Speech?", default=False):
            prompter.secho("\n[SECURITY WARNING] Azure Keys are sensitive secrets.", color="red", bold=True)
            prompter.echo("We will store your key and region ENCRYPTED in the local Secret Manager.")
            prompter.echo("You should NEVER commit these keys to git.\n")
            
            prompter.echo("Enter Azure Speech Key (masked):")
            key = prompter.getpass("Key: ")  # no-preflight-check
            region = prompter.prompt("Azure Region (e.g. eastus): ")
            
            if key and region:
                # Security: Validate region
                import re
                if not re.match(r"^[a-z0-9-]+$", region):
                     prompter.secho("[ERROR] Invalid region format. Must be alphanumeric/hyphens only.", color="red")
                else:
                    try:
                        # Enforce secure storage for KEY and REGION
                        manager.set_secret("azure", "key", key)  # no-preflight-check
                        manager.set_secret("azure", "region", region)  # no-preflight-check
                        
                        # We also update config for visibility if user wants, but reliance should be on secret?
                        # Security Review said "Cleartext storage of Azure region... might be seen as configuration".
                        # We will REMOVE it from plain config to satisfy them.
                        
                        prompter.secho("[OK] Azure credentials (Key & Region) stored in Secret Manager.", color="green")
                    except Exception as e:
                        prompter.secho(f"[ERROR] Failed to save Azure secret: {e}", color="red")
    else:
        prompter.secho("[OK] Azure key already configured.", color="green", dim=True)

    # 3. Google Cloud Speech
    if not manager.has_secret("google", "application_credentials_json"):
        if prompter.confirm("Do you want to enable Google Cloud Speech?", default=False):
            prompter.secho("\n[SECURITY WARNING] Service Account Keys are highly sensitive.", color="red", bold=True)
            prompter.echo("We will import the CONTENT of your JSON key and store it ENCRYPTED.")
            prompter.echo("We do NOT store the file path. You should DELETE the local JSON file after import.")
            prompter.echo("NEVER commit the JSON file to git.\n")
            
            prompter.echo("Enter path to Service Account JSON file (for one-time import):")
            path_str = prompter.prompt("Path: ", default="")
            
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
                        manager.set_secret("google", "application_credentials_json", json_content)  # no-preflight-check
                        prompter.secho("[OK] Google Service Account imported to Secret Manager.", color="green")
                        
                        if prompter.confirm("Delete local JSON file now (Recommended)?", default=True):
                            try:
                                path.unlink()
                                prompter.secho(f"[OK] Deleted {path.name}", color="green")
                            except Exception as e:
                                prompter.secho(f"[ERROR] Failed to delete file: {e}", color="red")
                        else:
                             prompter.secho(f"[ACTION REQUIRED] Please DELETE the file '{path.name}' manually.", color="yellow", bold=True)
                        
                    except Exception as e:
                        prompter.secho(f"[ERROR] Failed to import Google JSON: {e}", color="red")
                else:
                    prompter.secho(f"[WARN] File not found: {path}", color="yellow")
    else:
        prompter.secho("[OK] Google credentials already configured.", color="green", dim=True)

    # 4. Voice LLM Provider
    # Load existing
    try:
        data = config.load_yaml(voice_config_path)
    except FileNotFoundError:
        data = {}
        
    current_provider = config.get_value(data, "llm.provider") or "openai"
    
    if prompter.confirm(f"Configure Voice LLM? (Current: {current_provider})", default=False):
        # reuse PROVIDERS dict keys but filter for LLMs
        llm_providers = ["openai", "anthropic", "gemini"]
        
        prompter.echo("Select Voice LLM Provider:")
        for i, p in enumerate(llm_providers, 1):
            prompter.echo(f"{i}. {p}")
            
        choice = prompter.prompt("Enter number", default="1")
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(llm_providers):
                new_provider = llm_providers[idx]
                config.set_value(data, "llm.provider", new_provider)
                config.save_yaml(voice_config_path, data)
                prompter.echo(f"[OK] Voice LLM set to '{new_provider}'.")
        except ValueError:
            pass

    # 5. Local Models (Kokoro)
    if prompter.confirm("Download Local Voice Models (Kokoro)? (Recommended for Dev/Offline)", default=False):
        prompter.echo("Downloading models... This may take a moment.")
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
            prompter.secho("[OK] Local models downloaded.", color="green")
        except subprocess.CalledProcessError:
            prompter.secho("[ERROR] Failed to download models.", color="red")
        except Exception as e:
            prompter.secho(f"[ERROR] Unexpected error: {e}", color="red")

def configure_notion_settings(prompter: Prompter) -> None:
    """Configures Notion integration settings effectively bootstrapping the environment.
    
    Prompts the user for Notion Integration Token and Parent Page ID.
    Stores these secrets in the Secret Manager.
    Triggers the schema manager script to bootstrap database structures.
    """
    logger.info("Configuring Notion workspace settings", extra={"step": "configure_notion_settings"})
    prompter.echo("\n[INFO] Configuring Notion Workspace Manager...")
    
    manager = get_secret_manager()
    
    # 1. Notion Token
    token = get_secret("notion_token", service="notion") or os.getenv("NOTION_TOKEN")
    if not token:
        if prompter.confirm("Configure Notion Integration?", default=False):
            token = prompter.getpass("Notion Integration Token: ")  # no-preflight-check
            if token:
                try:
                    # Save to 'notion' service
                    manager.set_secret("notion", "notion_token", token)  # no-preflight-check
                    # Also set in env for immediate use
                    os.environ["NOTION_TOKEN"] = token
                    prompter.secho("[OK] Notion Token saved.", color="green")
                except Exception as e:
                    prompter.secho(f"[ERROR] Failed to save token: {e}", color="red")
        else:
            prompter.echo("Skipping Notion setup.")
            return

    # 2. Parent Page ID
    agent_config = config.load_yaml(config.etc_dir / "agent.yaml")
    page_id = config.get_value(agent_config, "notion.page_id") or os.getenv("NOTION_PARENT_PAGE_ID")
    if not page_id:
        prompter.echo("We need a Parent Page ID where the Agent will create databases.")
        prompter.echo("Tips: You can copy the full URL of the page.")
        page_id = prompter.prompt("Notion Parent Page URL or ID: ", default="")
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
                         prompter.secho(f"[INFO] Extracted Page ID: {page_id}", dim=True)
                
                config.set_value(agent_config, "notion.page_id", page_id)
                config.save_yaml(config.etc_dir / "agent.yaml", agent_config)
                # Ensure env var is set for current process usage (e.g. bootstrap script)
                os.environ["NOTION_PARENT_PAGE_ID"] = page_id
                prompter.secho("[OK] Page ID saved.", color="green")
            except Exception as e:
                prompter.secho(f"[ERROR] Failed to save Page ID: {e}", color="red")
    
    # 3. Trigger Bootstrap
    if token and page_id:
        if prompter.confirm("Run Notion Schema Bootstrap now?", default=True):
            prompter.echo("Running Schema Manager... (This launches an MCP server)")
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
                prompter.secho("[SUCCESS] Notion Environment Bootstrapped!", color="green")
            except subprocess.CalledProcessError:
                prompter.secho("[ERROR] Schema Manager failed.", color="red")
            except Exception as e:
                 prompter.secho(f"[ERROR] Unexpected error running script: {e}", color="red")

def configure_mcp_settings(prompter: Prompter) -> None:
    """Configures optional MCP servers like NotebookLM."""
    logger.info("Configuring MCP settings", extra={"step": "configure_mcp_settings"})
    prompter.echo("\n[INFO] Configuring MCP Integrations...")
    
    agent_config_path = config.etc_dir / "agent.yaml"
    try:
        data = config.load_yaml(agent_config_path)
    except FileNotFoundError:
        data = {}
        
    mcp_servers = config.get_value(data, "agent.mcp.servers") or {}
    
    if "notebooklm" not in mcp_servers:
        if prompter.confirm("Do you want to configure the Google NotebookLM MCP server?", default=False):
            prompter.echo("This requires 'uv' to be installed.")
            
            # Add to agent.yaml
            from agent.core.config import DEFAULT_MCP_SERVERS
            mcp_servers["notebooklm"] = DEFAULT_MCP_SERVERS["notebooklm"]
            config.set_value(data, "agent.mcp.servers", mcp_servers)
            config.save_yaml(agent_config_path, data)
            prompter.secho("[OK] NotebookLM MCP server added to local configuration.", color="green")
            
            # Optionally run the auth command
            if prompter.confirm("Would you like to authenticate NotebookLM now (opens browser)?", default=True):
                try:
                    prompter.echo("Running notebooklm-mcp-auth...")
                    subprocess.run(
                        ["uv", "tool", "run", "--from", "notebooklm-mcp-server", "notebooklm-mcp-auth"],
                        check=True
                    )
                    prompter.secho("[SUCCESS] NotebookLM authentication completed.", color="green")
                except subprocess.CalledProcessError:
                    prompter.secho("[ERROR] Failed to authenticate NotebookLM.", color="red")
                except FileNotFoundError:
                    prompter.secho("[ERROR] 'uv' is not installed or not in PATH.", color="red")
        else:
            prompter.echo("Skipping NotebookLM setup.")
    else:
        prompter.secho("[OK] NotebookLM MCP is already configured.", color="green", dim=True)



