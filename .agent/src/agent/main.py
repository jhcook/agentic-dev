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

import logging
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console

from agent.commands import (
    adr,
    check,
    config,
    implement,
    lint,
    match,
    plan,
    query,
    runbook,
    secret,
    story,
    visualize,
    workflow,
)
from agent.commands import list as list_cmd


console = Console(stderr=True)

app = typer.Typer(
    name="agent",
    help="Governed workflow CLI for the Inspected application",
    add_completion=False,
    pretty_exceptions_enable=False,  # Disable stack traces for users
)

app.add_typer(config.app, name="config")
app.add_typer(secret.app, name="secret")

app.command(name="new-story")(story.new_story)
app.command(name="new-plan")(plan.new_plan)
app.command(name="new-adr")(adr.new_adr)
app.command(name="new-runbook")(runbook.new_runbook)
app.command(name="implement")(implement.implement)

app.command(name="list-stories")(list_cmd.list_stories)
app.command(name="list-plans")(list_cmd.list_plans)
app.command(name="list-runbooks")(list_cmd.list_runbooks)
app.command(name="list-models")(list_cmd.list_models)

app.command(name="validate-story")(check.validate_story)
app.command(name="preflight")(check.preflight)
app.command(name="impact")(check.impact)
app.command(name="panel")(check.panel)
app.command(name="run-ui-tests")(check.run_ui_tests)
app.command(name="match-story")(match.match_story)

app.command(name="pr")(workflow.pr)
app.command(name="commit")(workflow.commit)
app.command(name="lint")(lint.lint)
app.command(name="query")(query.query)

# Register visualize Click group with Typer
# visualize.py uses Click @click.group(), so we register the Click group directly

@app.command(name="visualize", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def visualize_cmd(ctx: typer.Context):
    """
    Generate Mermaid diagrams of project artifacts.
    
    Subcommands:
      graph  - Generate full dependency graph
      flow   - Show flow for a specific story
    """
    # Forward to the Click group
    from click.testing import CliRunner
    
    # Use Click's invoke directly
    runner = CliRunner()
    result = runner.invoke(visualize.visualize, ctx.args)
    typer.echo(result.output)
    if result.exit_code != 0:
        raise typer.Exit(code=result.exit_code)

try:
    from agent.commands import onboard
    app.command(name="onboard")(onboard.onboard)
except ImportError:
    pass

from agent.sync import cli as sync_cli

app.add_typer(sync_cli.app, name="sync")

def setup_logging():
    """Configure global logging to file and console."""
    log_dir = Path(".agent/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "agent.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            # Note: We rely on Rich Console for stdout, so we don't add a StreamHandler here
            # to avoid duplicate/ugly output in the terminal.
        ]
    )

console = Console()

@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(
        None, "--version", help="Show version and exit"
    ),
    provider: str = typer.Option(
        None, "--provider", help="Force AI provider (gh, gemini, openai)"
    ),
):
    """
    Agent CLI - Governance and Workflow Automation
    """
    setup_logging()

    if version:
        ver = "unknown"
        try:
            ver = subprocess.check_output(["git", "describe", "--tags", "--always", "--dirty"]).decode().strip()
        except Exception:
            try:
                # Fallback to file
                # .agent/src/agent/main.py -> .agent/src/VERSION
                version_file = Path(__file__).parent.parent / "VERSION"
                if version_file.exists():
                    ver = version_file.read_text().strip()
            except Exception:
                pass
        
        if ver == "unknown":
             ver = "v0.1.0" # Legacy fallback

        typer.echo(f"Agent CLI {ver}")
        raise typer.Exit()

    if provider:
        try:
            from agent.core.ai import ai_service
            ai_service.set_provider(provider)
        except (ValueError, RuntimeError):
            # Error message already printed by set_provider
            raise typer.Exit(code=1)

if __name__ == "__main__":
    app()

