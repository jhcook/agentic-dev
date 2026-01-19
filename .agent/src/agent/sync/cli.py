import typer
from agent.sync import sync as sync_ops

app = typer.Typer(
    help="Distributed synchronization (push, pull, status, scan).",
    no_args_is_help=True
)

@app.command()
def pull():
    """Pull artifacts from remote."""
    sync_ops.sync()

@app.command()
def push():
    """Push artifacts to remote."""
    print("Push functionality not yet implemented.")

@app.command()
def status(detailed: bool = typer.Option(False, "--detailed", help="Show detailed list of artifacts")):
    """Check sync status."""
    sync_ops.status(detailed=detailed)

@app.command()
def delete(
    id: str = typer.Argument(..., help="Artifact ID to delete"),
    type: str = typer.Option(None, "--type", help="Specific artifact type (story, plan, runbook, adr)")
):
    """Delete artifact from local cache."""
    sync_ops.delete(id, type)
