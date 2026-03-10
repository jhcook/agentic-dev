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

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from opentelemetry import trace
from agent.core.onboard.prompter import Prompter



# Note: This command requires `typer` and `python-dotenv`.
# Ensure they are added to your project's dependencies.

# from agent.core.ai.service import PROVIDERS, AIService, ai_service # Moved to local imports
from agent.core.config import config
from agent.core.secrets import (
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

def check_dependencies(prompter: Prompter) -> bool:
    """Verifies that required system dependencies are installed."""
    logger.info("Starting dependency check", extra={"step": "check_dependencies"})
    prompter.echo("[INFO] Checking for required system dependencies...")
    # As per @Security review, add any binary dependencies here. e.g., `git`
    dependencies = ["git", "python3", "gh"]
    recommended = ["node", "npm"]

    all_found = True
    for dep in dependencies:
        if not shutil.which(dep):
            prompter.secho(
                f"[ERROR] Binary dependency not found: '{dep}'. Please install it.",
                color="red",
            )
            all_found = False
        else:
            prompter.secho(f"  - Found binary: {dep}", color="green")

    # Check Python dependencies
    python_deps = [
        ("dotenv", "python-dotenv"),
        ("mcp", "modelcontextprotocol"),
        ("typer", "typer"),
    ]
    
    import importlib.util
    for module_name, package_name in python_deps:
        if not importlib.util.find_spec(module_name):
            prompter.secho(
                f"[ERROR] Python dependency not found: '{package_name}' ({module_name}).\n"
                f"        Please run: pip install -e .agent",
                color="red",
            )
            all_found = False
        else:
            prompter.secho(f"  - Found module: {module_name}", color="green")

    if not all_found:
        return False

    # Check recommended
    for dep in recommended:
        if not shutil.which(dep):
            prompter.secho(
                f"[WARN] Recommended dependency not found: '{dep}'. Some features may be limited.",
                color="yellow",
            )
        else:
            prompter.secho(f"  - Found {dep} (recommended)", color="green")
            
    # Check linting tools
    if not shutil.which("markdownlint"):
         prompter.secho("[INFO] markdownlint-cli not found. It is recommended for documentation checks.", color="blue")
         if prompter.confirm("Install markdownlint-cli globally via npm?", default=True):
             if shutil.which("npm"):
                 try:
                     subprocess.run(["npm", "install", "-g", "markdownlint-cli"], check=True)
                     prompter.secho("[OK] markdownlint-cli installed.", color="green")
                 except Exception as e:
                     prompter.secho(f"[ERROR] Failed to install markdownlint-cli: {e}", color="red")
             else:
                 prompter.secho("[WARN] npm not found. Cannot install markdownlint-cli automatically.", color="yellow")
    else:
         prompter.secho("  - Found tool: markdownlint", color="green")

    prompter.secho("[OK] System dependencies check passed.", color="green")
    return True


def check_github_auth(prompter: Prompter) -> bool:
    """Checks GitHub authentication via MCP and CLI (Unified)."""
    logger.info("Configuring GitHub Auth", extra={"step": "check_github_auth"})
    prompter.echo("\n[INFO] Configuring GitHub Access...")

    # Ensure gh is available
    if not shutil.which("gh"):
        prompter.secho(
            "[ERROR] GitHub CLI ('gh') is required but not found. Please install it.",
            color="red"
        )
        return False

    # Check if already authenticated via gh
    gh_status = subprocess.run(
        ["gh", "auth", "status"], capture_output=True, text=True
    )
    gh_logged_in = gh_status.returncode == 0
    
    # Check if secret already exists
    manager = get_secret_manager()
    secret_exists = manager.is_initialized() and manager.is_unlocked() and manager.has_secret("github", "token")

    if gh_logged_in and secret_exists:
        prompter.secho("[OK] GitHub access already configured (CLI & MCP).", color="green")
        if not prompter.confirm("Would you like to re-configure?", default=False):
            return True

    prompter.echo("\n[INFO] We will now configure GitHub access for both the Agent (MCP) and CLI (gh).")
    prompter.echo("You will need a GitHub Personal Access Token (PAT) with scopes: repo, read:org")

    token = prompter.getpass("GitHub PAT: ")  # no-preflight-check
    if not token:
        prompter.secho("[WARN] No token provided. Skipping GitHub configuration.", color="yellow")
        return False

    # 1. Configure MCP Secret
    try:
        if manager.is_initialized():
             if not manager.is_unlocked():
                  prompter.echo("Secret manager is locked. Please unlock to save access token.")
                  # We rely on previous steps ensuring it's unlocked or prompt
                  # But actually onboard runs sequentially, so it should be unlocked.
                  pass
             
             manager.set_secret("github", "token", token)  # no-preflight-check
             prompter.secho("  - [OK] Agent MCP token saved securely.", color="green")
             
             # Set generic config to 'mcp' as primary tool for agent, though 'gh' is also available
             agent_config_path = config.etc_dir / "agent.yaml"
             try:
                 data = config.load_yaml(agent_config_path)
             except FileNotFoundError:
                 data = {}
             config.set_value(data, "agent.github.tool", "mcp")
             config.save_yaml(agent_config_path, data)
             
    except Exception as e:
        prompter.secho(f"  - [ERROR] Failed to save MCP token: {e}", color="red")

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
            prompter.secho("  - [OK] GitHub CLI authenticated.", color="green")
        else:
             prompter.secho(f"  - [ERROR] GitHub CLI login failed: {stderr.strip() if stderr else 'Unknown error'}", color="red")
             
    except Exception as e:
         prompter.secho(f"  - [ERROR] Failed to run gh auth: {e}", color="red")

    prompter.secho("[OK] GitHub access configuration complete.", color="green")
    return True


def ensure_agent_directory(prompter: Prompter, project_root: Optional[Path] = None) -> None:
    """Ensures the .agent directory exists and is a directory."""
    logger.info("Ensuring agent workspace exists", extra={"step": "ensure_agent_directory"})
    root = project_root or Path(".").resolve()
    agent_dir = root / ".agent"

    prompter.echo("\n[INFO] Checking for '.agent' workspace directory...")
    try:
        if agent_dir.exists() and not agent_dir.is_dir():
            prompter.secho(
                "[ERROR] A file named '.agent' exists. Please remove it and run again.",
                color="red",
            )
            prompter.exit(1)
        agent_dir.mkdir(exist_ok=True)
        prompter.secho("[OK] '.agent' directory is present.", color="green")
    except OSError as e:
        prompter.secho(f"[ERROR] Failed to create '.agent' directory: {e}", color="red")
        prompter.exit(1)


def ensure_gitignore(prompter: Prompter, project_root: Optional[Path] = None) -> None:
    """Ensures .env is listed in .gitignore to prevent accidental secret exposure."""
    logger.info("Ensuring agent metadata is gitignored", extra={"step": "ensure_gitignore"})
    root = project_root or Path(".").resolve()
    gitignore_file = root / ".gitignore"

    prompter.echo("\n[INFO] Verifying '.gitignore' configuration...")
    try:
        if not gitignore_file.exists():
            gitignore_file.touch()
            prompter.echo("[INFO] Created missing '.gitignore' file.")

        with gitignore_file.open("r+") as f:
            lines = f.readlines()
            # Check if '.env' is on a line by itself
            is_present = any(line.strip() == ".env" for line in lines)
            if not is_present:
                prompter.echo("[INFO] Adding '.env' to '.gitignore'.")
                f.seek(0, 2)  # Go to end of file
                if lines and not lines[-1].endswith("\n"):
                    f.write("\n")
                f.write("\n# Agent secrets\n.env\n")
            else:
                prompter.secho(
                    "[OK] '.env' is already in '.gitignore'.", color="green", dim=True
                )
    except PermissionError:
        prompter.secho(
            "[ERROR] Could not write to '.gitignore'. Please check file permissions.",
            color="red",
        )
        prompter.exit(1)
    except OSError as e:
        prompter.secho(f"[ERROR] Failed to read or write '.gitignore': {e}", color="red")
        prompter.exit(1)


def setup_frontend(prompter: Prompter) -> None:
    """
    Installs frontend dependencies using npm.
    
    Observability:
    - Uses OpenTelemetry to trace the installation duration and success/failure.
    - All telemetry is strictly local/stdio unless an exporter is explicitly configured by the user.
    - No PII is captured.
    """
    logger.info("Setting up admin console frontend", extra={"step": "setup_frontend"})
    prompter.echo("\n[INFO] Setting up Frontend...")

    web_dir = AGENT_DIR / "src" / "web"
    
    # 1. Check if npm is installed
    if not shutil.which("npm"):
        prompter.secho(
            "[WARN] 'npm' not found. Skipping frontend setup.",
            color="yellow"
        )
        prompter.echo("The Agent Admin Console frontend may not work until you install Node.js and run 'npm install' manually.")
        return

    # 2. Check directory
    if not web_dir.exists():
        prompter.secho(
            f"[WARN] Web directory not found at {web_dir}. Skipping frontend setup.",
            color="yellow"
        )
        return

    # 3. Install dependencies
    prompter.echo("Installing Node dependencies... (this may take a minute)")
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
             
        prompter.secho("[OK] Frontend dependencies installed.", color="green")
        
        # 4. Security Audit
        # 4. Security Audit
        prompter.echo("Running security audit on dependencies...")
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
             prompter.secho("[WARN] Failed to run security audit.", color="yellow")
             
    except subprocess.CalledProcessError as e:
        prompter.secho(
            f"[ERROR] Failed to run 'npm install': {e}",
            color="red"
        )
        prompter.echo("You may need to resolve this manually to use the Admin Console.")



def run_verification(prompter: Prompter) -> None:
    """Verifies AI connectivity with a Hello World prompt."""
    logger.info("Verifying AI connectivity", extra={"step": "run_verification"})
    prompter.echo("\n[INFO] Verifying AI connectivity...")
    
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
            prompter.secho(
                "[SUCCESS] AI Connectivity Verified! 🚀",
                color="green",
                bold=True
            )
        else:
            prompter.secho(
                f"[WARN] AI returned unexpected response: {response}",
                color="yellow"
            )
    except Exception as e:
        prompter.secho(f"[ERROR] Verification failed: {e}", color="red")


def display_next_steps(prompter: Prompter) -> None:
    """Displays a guided tour of next steps."""
    prompter.echo("\n🎉 You are all set! Here is a quick tour of what you can do:")
    
    columns = ["Command", "Description"]
    rows = [
        ["agent story", "Start a new feature or bugfix (creates a Story artifact)"],
        ["agent preflight", "Run governance checks (preflight) on your code"],
        ["agent pr", "Create a Pull Request with all checks passing"],
        ["agent list-models", "See available AI models"],
        ["agent config list", "View your current configuration"],
    ]
    
    prompter.print_table("Next Steps Tour", columns, rows)
    prompter.echo("\nTip: Use --help on any command for more info.")
