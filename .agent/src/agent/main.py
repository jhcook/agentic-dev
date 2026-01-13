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
from rich.console import Console

from agent.commands import story, plan, adr
from agent.commands import list as list_cmd
from agent.commands import check, workflow
from agent.commands import runbook, implement, match
from agent.sync import sync

app = typer.Typer(
    name="agent",
    help="Governed workflow CLI for the Inspected application",
    add_completion=False,
)

app.command(name="new-story")(story.new_story)
app.command(name="new-plan")(plan.new_plan)
app.command(name="new-adr")(adr.new_adr)
app.command(name="new-runbook")(runbook.new_runbook)
app.command(name="implement")(implement.implement)

app.command(name="list-stories")(list_cmd.list_stories)
app.command(name="list-plans")(list_cmd.list_plans)
app.command(name="list-runbooks")(list_cmd.list_runbooks)

app.command(name="validate-story")(check.validate_story)
app.command(name="preflight")(check.preflight)
app.command(name="impact")(check.impact)
app.command(name="panel")(check.panel)
app.command(name="run-ui-tests")(check.run_ui_tests)
app.command(name="match-story")(match.match_story)

app.command(name="pr")(workflow.pr)
app.command(name="commit")(workflow.commit)

# Sync integration using Typer
# Since sync.py uses argparse, we'll wrap it or just use subprocess for now 
# TO keep it clean, let's just make a shim here.
@app.command(name="sync", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def sync_cmd(ctx: typer.Context):
    """
    Distributed synchronization (push, pull, status, scan).
    """
    # Forward arguments to sync.main
    # Sys.argv hack or just call logic?
    # sync.main() uses argparse which reads sys.argv.
    # We need to reconstruct sys.argv for the sync tool.
    import sys
    # sys.argv will be ['agent', 'sync', 'status', ...]
    # sync.main expects ['...sync.py', 'status'] or just the args.
    # Let's adjust sys.argv to strip 'agent' and 'sync' prefix for the parser relative 
    
    # Actually simpler: sync.py uses argparse which parses sys.argv[1:] by default?
    # If we call main(), it parses existing sys.argv.
    # existing sys.argv: ['.../main...py', 'sync', 'status']
    # sync.py expects: ['script', 'status']
    
    # Let's fake it.
    sys.argv = ["agent-sync"] + ctx.args
    sync.main()

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
    if version:
        try:
            import subprocess
            ver = subprocess.check_output(["git", "describe", "--tags", "--always", "--dirty"]).decode().strip()
        except Exception:
            ver = "v0.1.0"
        typer.echo(f"Agent CLI {ver}")
        raise typer.Exit()

    if provider:
        from agent.core.ai import ai_service
        ai_service.set_provider(provider)

if __name__ == "__main__":
    app()
