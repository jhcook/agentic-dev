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

"""Agent Onboarding Proxy Facade.

This module provides the Typer CLI commands for the `agent onboard` workflow.
It serves as a thin facade, proxying all actual implementation logic to the
`agent.core.onboard.steps` module to support independence and testability.
"""

import typer
from pathlib import Path
from opentelemetry import trace
from rich.console import Console

from agent.core.onboard import steps

app = typer.Typer()
console = Console()
tracer = trace.get_tracer(__name__)

# Proxies for testing backward compatibility and logic isolation
def check_dependencies() -> None:
    """Proxy for check_dependencies step."""
    if not steps.check_dependencies(console):
        raise typer.Exit(code=1)

def check_github_auth() -> None:
    """Proxy for check_github_auth step."""
    if not steps.check_github_auth(console):
        raise typer.Exit(code=1)

def ensure_agent_directory(project_root: Path = None) -> None:
    """Proxy for ensure_agent_directory step."""
    steps.ensure_agent_directory(console, project_root)

def ensure_gitignore(project_root: Path = None) -> None:
    """Proxy for ensure_gitignore step."""
    steps.ensure_gitignore(console, project_root)

def configure_api_keys() -> None:
    """Proxy for configure_api_keys step."""
    steps.configure_api_keys(console)

def configure_agent_settings() -> None:
    """Proxy for configure_agent_settings step."""
    steps.configure_agent_settings(console)

def select_default_model(provider: str, config_data: dict, config_path: Path) -> None:
    """Proxy for select_default_model step."""
    steps.select_default_model(console, provider, config_data, config_path)

def configure_voice_settings() -> None:
    """Proxy for configure_voice_settings step."""
    steps.configure_voice_settings(console)

def configure_notion_settings() -> None:
    """Proxy for configure_notion_settings step."""
    steps.configure_notion_settings(console)

def configure_mcp_settings() -> None:
    """Proxy for configure_mcp_settings step."""
    steps.configure_mcp_settings(console)

def setup_frontend() -> None:
    """Proxy for setup_frontend step."""
    steps.setup_frontend(console)

def run_verification() -> None:
    """Proxy for run_verification step."""
    steps.run_verification(console)

def display_next_steps() -> None:
    """Proxy for display_next_steps step."""
    steps.display_next_steps(console)

@app.command()
def onboard() -> None:
    """Initialize the Agent environment and configure integrations."""
    with tracer.start_as_current_span("agent_onboard"):
        console.print("[bold]Starting Agent Onboarding[/bold]\n")
        
        check_dependencies()
        ensure_agent_directory()
        ensure_gitignore()
        configure_api_keys()
        check_github_auth()
        configure_agent_settings()
        configure_voice_settings()
        configure_notion_settings()
        configure_mcp_settings()
        run_verification()
        
        import typer
        typer.secho(
            "\n[SUCCESS] Onboarding complete! The agent is ready to use.",
            fg=typer.colors.GREEN,
            bold=True,
        )
        display_next_steps()