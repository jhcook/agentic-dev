import typer

from agent.commands.onboard import app as onboard_app

app = typer.Typer()
app.add_typer(onboard_app, name="onboard")


@app.callback()
def cli() -> None:
    """A CLI for managing and interacting with the AI agent."""
    pass


if __name__ == "__main__":
    app()