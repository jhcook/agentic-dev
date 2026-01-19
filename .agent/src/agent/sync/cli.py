import typer
from agent.sync import sync as sync_ops

app = typer.Typer(
    help="Distributed synchronization (push, pull, status, scan).",
    no_args_is_help=True
)

@app.command()
def pull(verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output")):
    """Pull artifacts from remote."""
    sync_ops.sync(verbose=verbose)

@app.command()
def push(verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output")):
    """Push artifacts to remote."""
    sync_ops.push(verbose=verbose)

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

@app.command()
def scan(verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output")):
    """Scan local file system and update cache."""
    sync_ops.scan(verbose=verbose)
