import typer
from rich.console import Console

from agent.commands import story, plan, adr
from agent.commands import list as list_cmd
from agent.commands import check, workflow
from agent.commands import runbook, implement, match

app = typer.Typer(
    name="agent",
    help="Governed workflow CLI for the Inspected application",
    add_completion=False,
)

app.command(name="new-story")(story.new_story)
app.command(name="new-plan")(plan.new_plan)
app.command(name="plan")(plan.plan)
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
