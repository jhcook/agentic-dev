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
)

app = typer.Typer()


@app.command()
def hello(name: str):
    """
    Say hello.
    """
    print(f"Hello {name}")


# Governance & Quality
app.command()(lint.lint)
app.command()(check.preflight)
app.command()(check.impact)
app.command()(check.panel)
app.command(name="run-ui-tests")(check.run_ui_tests)
app.command("audit")(audit.audit)



# Workflows
app.command()(workflow.commit)
app.command()(workflow.pr)
app.command()(implement.implement)
app.command(name="new-story")(story.new_story)

app.command(name="new-runbook")(runbook.new_runbook)

app.command(name="new-adr")(adr.new_adr)


# Infrastructure
app.command(name="onboard")(onboard.onboard)

@app.command(name="sync")
def sync_cmd(cursor: str = None):
    """
    Sync artifacts to the local database.
    """
    try:
        from agent.sync import main as sync_module
        sync_module.sync_data(cursor=cursor)
    except ImportError as e:
        typer.echo(f"Error loading sync module: {e}")
        typer.echo("Missing dependency? Try 'pip install memory_profiler'")
        raise typer.Exit(1)

# Sub-commands (Typer Apps)
app.add_typer(admin.app, name="admin")
app.add_typer(config.app, name="config")
app.add_typer(mcp.app, name="mcp")
app.add_typer(secret.app, name="secret")

# List Commands
app.command("list-stories")(list_cmd.list_stories)
app.command("list-plans")(list_cmd.list_plans)
app.command("list-runbooks")(list_cmd.list_runbooks)
app.command("list-models")(list_cmd.list_models)

# Helper Commands
app.command("match-story")(match.match_story)
app.command("validate-story")(check.validate_story)
app.command("new-plan")(plan.new_plan)


if __name__ == "__main__":
    app()