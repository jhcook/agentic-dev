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

import typer

from agent.commands import (
    admin,
    adr,
    audit,
    check,
    config,
    implement,
    importer,
    journey,
    lint,
    list as list_cmd,
    match,
    mcp,
    onboard,
    plan,
    runbook,
    secret,
    story,
    workflow,
    query,
)

app = typer.Typer()


@app.callback(invoke_without_command=True)
def cli(
    ctx: typer.Context,
    verbose: int = typer.Option(0, "--verbose", "-v", count=True, help="Increase verbosity level."),
    version: bool = typer.Option(None, "--version", help="Show version and exit"),
    provider: str = typer.Option(None, "--provider", help="Force AI provider (gh, gemini, openai)")
) -> None:
    """A CLI for managing and interacting with the AI agent."""
    from agent.core.logger import configure_logging
    configure_logging(verbose)

    if version:
        try:
            from pathlib import Path
            version_file = Path(__file__).parent.parent / "VERSION"
            ver = version_file.read_text().strip() if version_file.exists() else "unknown"
        except Exception:
            ver = "unknown"
        typer.echo(f"Agent CLI {ver}")
        raise typer.Exit()

    if provider:
        try:
            from agent.core.ai import ai_service
            ai_service.set_provider(provider)
        except Exception as e:
            typer.echo(f"Error setting provider: {e}")
            raise typer.Exit(1)

    if ctx.invoked_subcommand is None:
         # Restoring default behavior: missing command is an error (unless version/provider handled above)
         typer.echo(ctx.get_help())
         # Exit with 1 or 2 to satisfy "!= 0" tests asserting missing command
         raise typer.Exit(1)


@app.command()
def help(ctx: typer.Context):
    """Show help for the CLI."""
    typer.echo(ctx.parent.get_help())
    raise typer.Exit()





# Governance & Quality
app.command()(lint.lint)
from agent.core.auth.decorators import with_creds

# Governance & Quality
app.command()(lint.lint)
app.command()(with_creds(check.preflight))
app.command()(with_creds(check.impact))
app.command()(with_creds(check.panel))
app.command(name="run-ui-tests")(check.run_ui_tests)
app.command("audit")(audit.audit)



# Workflows
app.command()(with_creds(workflow.commit))
app.command()(with_creds(workflow.pr))
app.command()(with_creds(implement.implement))
app.command(name="new-story")(with_creds(story.new_story))

app.command(name="new-runbook")(with_creds(runbook.new_runbook))
app.command(name="new-journey")(journey.new_journey)
app.command(name="validate-journey")(journey.validate_journey)

app.command(name="new-adr")(adr.new_adr)


# Infrastructure
app.command(name="onboard")(onboard.onboard)
app.command(name="query")(query.query)

from agent.sync import cli as sync_cli
app.add_typer(sync_cli.app, name="sync")

# Sub-commands (Typer Apps)
app.add_typer(admin.app, name="admin")
app.add_typer(config.app, name="config")
app.add_typer(importer.app, name="import")
app.add_typer(mcp.app, name="mcp")
app.add_typer(secret.app, name="secret")

# List Commands
app.command("list-stories")(list_cmd.list_stories)
app.command("list-plans")(list_cmd.list_plans)
app.command("list-runbooks")(list_cmd.list_runbooks)
app.command("list-models")(list_cmd.list_models)
app.command("list-journeys")(list_cmd.list_journeys)

# Helper Commands
app.command("match-story")(with_creds(match.match_story))
app.command("validate-story")(check.validate_story)
app.command("new-plan")(with_creds(plan.new_plan))


if __name__ == "__main__":
    app()