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
import logging
import warnings
import os

# --- Suppress verbose AI / Embedding Library Logging Globally ---
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["ANONYMIZED_TELEMETRY"] = "False"

warnings.filterwarnings("ignore", module="huggingface_hub.*")
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("transformers.modeling_utils").setLevel(logging.ERROR)
logging.getLogger("backoff").setLevel(logging.ERROR)

warnings.filterwarnings("ignore", module="google.auth._default")
warnings.filterwarnings("ignore", message=".*Failed to initialize NumPy.*")

from agent.commands import (
    admin,
    adr,
    audit,
    check,
    config,
    console as console_cmd,
    implement,
    importer,
    impact,
    journey,
    license as license_cmd,
    lint,
    list as list_cmd,
    match,
    mcp,
    onboard,
    panel,
    plan,
    runbook,
    secret,
    story,
    visualize,
    voice,
    workflow,
    query,
    review_chat as review_chat_cmd,
    tests_ui,
)

app = typer.Typer()


@app.callback(invoke_without_command=True)
def cli(
    ctx: typer.Context,
    verbose: int = typer.Option(0, "--verbose", "-v", count=True, help="Increase verbosity level."),
    version: bool = typer.Option(None, "--version", help="Show version and exit"),
    provider: str = typer.Option(None, "--provider", help="Force AI provider (gh, gemini, vertex, openai, anthropic)")
) -> None:
    """A CLI for managing and interacting with the AI agent."""
    # Environment variables loaded by config.py at import time (dotenv)

    from agent.core.logger import configure_logging
    configure_logging(verbose)

    from agent.core.telemetry import initialize_telemetry
    initialize_telemetry()

    if version:
        try:
            import sys
            from pathlib import Path

            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                base_path = Path(sys._MEIPASS)
            else:
                base_path = Path(__file__).parent.parent

            version_file = base_path / "VERSION"
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





from agent.core.auth.decorators import with_creds

# Governance & Quality
app.command()(lint.lint)
app.command()(check.preflight)
app.command()(with_creds(impact.impact))
app.command()(with_creds(panel.panel))
app.command(name="run-ui-tests")(tests_ui.run_ui_tests)
app.command("audit")(audit.audit)



# Workflows
app.command()(workflow.commit)
app.command()(workflow.pr)
app.command()(with_creds(implement.implement))
app.command(name="new-story")(story.new_story)

app.command(name="new-runbook")(with_creds(runbook.new_runbook))
app.command(name="new-journey")(journey.new_journey)
app.command(name="validate-journey")(journey.validate_journey)
app.command(name="review-voice")(with_creds(voice.review_voice))
app.command(name="review-chat")(review_chat_cmd.review_chat)

app.command(name="new-adr")(adr.new_adr)


# Infrastructure
app.command(name="onboard")(onboard.onboard)
app.command(name="query")(query.query)
app.command(name="console")(console_cmd.console)

from agent.sync import cli as sync_cli
app.add_typer(sync_cli.app, name="sync")

# Sub-commands (Typer Apps)
app.add_typer(admin.app, name="admin")
app.add_typer(config.app, name="config")
app.add_typer(importer.app, name="import")
app.add_typer(mcp.app, name="mcp")
app.add_typer(secret.app, name="secret")
app.add_typer(journey.app, name="journey")
app.add_typer(visualize.app, name="visualize")

# List Commands
app.command("list-stories")(list_cmd.list_stories)
app.command("list-plans")(list_cmd.list_plans)
app.command("list-runbooks")(list_cmd.list_runbooks)
app.command("list-models")(list_cmd.list_models)
app.command("list-journeys")(list_cmd.list_journeys)

# Helper Commands
app.command("match-story")(with_creds(match.match_story))
app.command("validate-story")(check.validate_story)
app.command("new-plan")(plan.new_plan)
app.command("apply-license")(license_cmd.apply_license)


def _assert_env() -> None:
    """Fail fast if critical runtime dependencies are missing.

    This catches the class of bugs where a package is missing from the active
    environment and causes silent downstream failures (caught exceptions,
    degraded behaviour, wrong log levels) rather than an obvious crash.

    Add entries here whenever a new hard dependency is introduced that is
    imported lazily or inside a try/except in production code paths.
    """
    import sys

    REQUIRED: list[tuple[str, str]] = [
        # (import_name, pip_name)
        # Only list packages that are:
        #  a) imported in hot production code paths (not try/except-guarded), AND
        #  b) not in the standard library.
        ("mistune", "mistune"),          # runbook S/R post-processing
        ("rich", "rich"),                # all console output
        ("typer", "typer"),              # CLI layer
        ("google.genai", "google-genai"),  # primary LLM backend (new SDK)
        ("pydantic", "pydantic"),        # model validation everywhere
        ("yaml", "pyyaml"),              # config + story parsing
    ]

    missing: list[str] = []
    for import_name, pip_name in REQUIRED:
        try:
            __import__(import_name)
        except ImportError:
            pkg = pip_name or import_name
            missing.append(pkg)

    if missing:
        typer.echo("❌ Environment check failed — missing required packages:", err=True)
        for pkg in missing:
            typer.echo(f"   pip install {pkg}", err=True)
        typer.echo("", err=True)
        typer.echo("   Are you running inside the project venv?  source .venv/bin/activate", err=True)
        sys.exit(1)


def main() -> None:
    """CLI entry point with top-level exception handling.

    Wraps ``app()`` so that any unhandled exception from any subcommand is
    displayed as a clean one-liner on stderr instead of a raw Python traceback.
    Pass ``-v`` or set ``AGENT_VERBOSE=1`` to see the full traceback.
    """
    import sys as _sys
    _assert_env()
    try:
        app()
    except SystemExit:
        # typer.Exit / typer.Abort use SystemExit — pass through normally.
        raise
    except KeyboardInterrupt:
        typer.echo("\n[Interrupted]", err=True)
        _sys.exit(130)
    except Exception as _exc:  # noqa: BLE001
        from agent.core.logger import get_logger as _get_logger
        _get_logger("main").exception(
            "Unhandled exception at CLI entry point",
            extra={"exc_type": type(_exc).__name__},
        )
        _verbose = os.environ.get("AGENT_VERBOSE", "0") not in ("0", "")
        if _verbose:
            import traceback as _tb
            _tb.print_exc()
        else:
            typer.echo(f"❌ {type(_exc).__name__}: {_exc}", err=True)
            typer.echo("   Run with -v for full traceback.", err=True)
        _sys.exit(1)


if __name__ == "__main__":
    main()