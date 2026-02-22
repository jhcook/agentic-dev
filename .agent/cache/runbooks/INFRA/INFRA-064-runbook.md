# INFRA-064: Standardize AI by Default and Graceful Degradation Across CLI Commands

## State

ACCEPTED

## Goal Description

Transition the CLI to an "AI by Default" paradigm, removing the need for explicit `--offline` flags. Implement graceful degradation when AI services are unavailable, either by falling back to manual workflows or exiting cleanly with informative messages.

## Linked Journeys

- JRN-006: Runbook File-Based Versioning System
- JRN-007: Implement Agent Impact Command
- JRN-057: Impact Analysis Workflow
- JRN-059: PR Creation Workflow
- JRN-060: Journey Creation Panel

## Panel Review Findings

**@Architect**:

- The proposed changes are significant and impact several CLI commands. It's essential to ensure that the new `--offline` flag is consistently implemented and documented across all affected commands.
- The `_ai_confirm_write()` utility function should be carefully designed to be generic enough to handle different types of content and target paths. Consider using a strategy pattern or similar to allow for customization.
- ADR-025 (Lazy AIService Initialization) is relevant and should be considered during implementation. We don't want to initialize the AI service unnecessarily when `--offline` is used.

**@Qa**:

- The Test Strategy section needs to be more comprehensive. We need specific test cases for each command in scope, covering both success and failure scenarios.
- The integration tests should also include cases where the AI service returns invalid data or takes too long to respond.
- Add a critical flow test for impact analysis workflow (JRN-057)

**@Security**:

- Ensure that the error messages displayed during graceful degradation do not leak any sensitive information about the system or the AI service.
- When falling back to `$EDITOR`, sanitize the input to prevent command injection vulnerabilities.
- The `_ai_confirm_write()` utility should not write any temporary files containing potentially sensitive data without proper encryption.

**@Product**:

- The Acceptance Criteria are clear and testable. However, consider adding a criterion to ensure that the transition to "AI by Default" is communicated to users effectively (e.g., through a release note or a one-time message in the CLI).
- Consider adding an alias for `--offline` like `--no-ai` to make it more intuitive for users.
- The "generate -> preview -> confirm" pattern needs to be crystal clear. Users need to have ultimate control and understanding of what is being written.

**@Observability**:

- The structured logs should include the specific command being executed, the AI service's response time, and any error messages encountered.
- Monitor the usage of the `--offline` flag to understand how often users are opting out of AI.
- Consider adding tracing to the AI service calls to identify performance bottlenecks.

**@Docs**:

- The documentation must be updated to reflect the removal of the `--offline` flag and the introduction of the `--offline` flag.
- The help text for each command needs to be updated to accurately describe the new behavior.
- Provide examples of how to use the `--offline`, `--write`, and `--dry-run` flags in different scenarios.

**@Compliance**:

- Ensure that the AI service being used is GDPR compliant.
- Review the data retention policies of the AI service.
- If any user data is being sent to the AI service, ensure that it is anonymized or pseudonymized.

**@Mobile**:

- N/A - This story focuses on the CLI, not the mobile app.

**@Web**:

- N/A - This story focuses on the CLI, not the web app.

**@Backend**:

- Ensure that the AI service calls are properly timed out to prevent the CLI from hanging indefinitely.
- Implement robust error handling to catch any exceptions raised by the AI service.
- Use type hints throughout the implementation to improve code maintainability and prevent runtime errors.

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Move common CLI argument parsing logic to a shared utility module in `agent/commands/utils.py`.
- [ ] Refactor error handling in `check.py` to use a consistent pattern with structured logging.
- [ ] Standardize help text formatting across all CLI commands.

## Implementation Steps

### commands/\_ai\_utils.py

#### NEW src/agent/commands/\_ai\_utils.py

- Create a new file `src/agent/commands/_ai_utils.py` to house the shared utility functions.
- Implement the `_ai_confirm_write(content, target_path, dry_run, write)` function to handle the preview and confirm logic. This function should:
  - Take the generated content, target path, `--dry-run` flag, and `--write` flag as input.
  - Display a rich preview of the content using `rich.panel.Panel`.
  - Prompt the user to confirm the write if neither `--dry-run` nor `--write` is specified.
  - Write the content to the target path if confirmed or if `--write` is specified.
  - Skip writing if `--dry-run` is specified.
  - Return a boolean indicating whether the write was successful.
- Implement the `_ai_preview_panel(content, title)` function to generate rich preview.
- Implement a generic error handler `_handle_ai_error(command_name, e)` to handle connection timeouts or other AI-related errors. Log the error and either fall back to manual input or exit cleanly, depending on the command type.

```python
# src/agent/commands/_ai_utils.py
import os
import logging
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

console = Console()
logger = logging.getLogger(__name__)

def _ai_confirm_write(content: str, target_path: Path, dry_run: bool = False, write: bool = False) -> bool:
    """
    Handles the preview and confirmation logic for writing AI-generated content to a file.
    """
    console.print(_ai_preview_panel(content, title=f"AI-Generated Content for {target_path}"))

    if dry_run:
        console.print("[bold blue]Dry run:[/bold blue] Skipping write to disk.")
        return False

    if write:
        target_path.write_text(content)
        console.print(f"[bold green]Wrote content to:[/bold green] {target_path}")
        return True

    if Confirm.ask(f"Write to {target_path}?"):
        target_path.write_text(content)
        console.print(f"[bold green]Wrote content to:[/bold green] {target_path}")
        return True
    else:
        console.print("[bold red]Cancelled:[/bold red] Write aborted.")
        return False

def _ai_preview_panel(content: str, title: str) -> Panel:
  return Panel(content, title=title, border_style="blue")

def _handle_ai_error(command_name: str, e: Exception):
    """
    Handles errors encountered when calling the AI service.
    """
    logger.error(f"Error calling AI service in {command_name}: {e}")
    console.print(f"[bold red]Error:[/bold red] Could not reach AI service. {e}")

    if command_name in ("new-story", "new-runbook", "journey new", "pr", "commit"):
        console.print("[bold yellow]Falling back to manual input in $EDITOR.[/bold yellow]")
        # Use typer.edit() for manual fallback
        import typer
        content = typer.edit()
        return content
    else:  # preflight, impact
        console.print("[bold red]Skipping AI analysis...[/bold red]")
        raise typer.Exit(code=1)
```

### commands/workflow.py

#### MODIFY src/agent/commands/workflow.py

- Remove the `--offline` flag from the `pr` and `commit` commands.
- Add an `--offline` flag to the `pr` and `commit` commands.
- Modify the command logic to use AI by default.
- Implement graceful degradation: if the AI service is unreachable, fall back to manual input using `$EDITOR`.
- Use the `_ai_confirm_write` utility function to handle preview and confirm logic.

```python
# src/agent/commands/workflow.py
import typer
from agent.commands._ai_utils import _ai_confirm_write, _handle_ai_error
def pr(
    story_id: str = typer.Option(..., help="Story ID"),
    offline: bool = typer.Option(False, "--offline", help="Disable AI and use manual input"),
    write: bool = typer.Option(False, "--write", help="Write to file without prompting"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without writing"),
):
    """
    Generates a pull request body using AI.
    """
    try:
        if offline:
            # Implement manual input using $EDITOR via typer.edit()
            content = typer.edit(text="<!-- \nManual input required. \nPlease enter your pull request body below.\n-->\n")
            if not content:
                console.print("[bold red]Aborted:[/bold red] No content provided.")
                raise typer.Exit(code=1)
        else:
            # Implement AI-powered pull request body generation
            content = "AI-generated pull request body." # Replace with actual logic

        target_path = Path("pr_body.md") # Or a better default location
        _ai_confirm_write(content, target_path, dry_run, write)
    except Exception as e:
        _handle_ai_error("pr", e)

def commit(
    story_id: str = typer.Option(..., help="Story ID"),
    offline: bool = typer.Option(False, "--offline", help="Disable AI and use manual input"),
    write: bool = typer.Option(False, "--write", help="Write to file without prompting"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without writing"),
):
   try:
        if offline:
            # Implement manual input using $EDITOR via typer.edit()
            content = typer.edit(text="<!-- \nManual input required. \nPlease enter your commit message below.\n-->\n")
            if not content:
                console.print("[bold red]Aborted:[/bold red] No content provided.")
                raise typer.Exit(code=1)
        else:
            # Implement AI-powered commit message generation
            content = "AI-generated commit message." # Replace with actual logic

        target_path = Path("commit_message.txt") # Or a better default location
        _ai_confirm_write(content, target_path, dry_run, write)
   except Exception as e:
        _handle_ai_error("commit", e)
```

### commands/story.py

#### MODIFY src/agent/commands/story.py

- Remove the `--offline` flag from the `new-story` command.
- Add an `--offline` flag to the `new-story` command.
- Modify the command logic to use AI by default.
- Implement graceful degradation: if the AI service is unreachable, fall back to manual input using `$EDITOR`.
- Use the `_ai_confirm_write` utility function to handle preview and confirm logic.

```python
# src/agent/commands/story.py
import typer
from agent.commands._ai_utils import _ai_confirm_write, _handle_ai_error
def new_story(
    title: str = typer.Option(..., help="Story title"),
    offline: bool = typer.Option(False, "--offline", help="Disable AI and use manual input"),
    write: bool = typer.Option(False, "--write", help="Write to file without prompting"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without writing"),
):
    try:
        if offline:
            # Implement manual input using $EDITOR via typer.edit()
            content = typer.edit(text=f"<!-- \nManual input required. \nPlease write your story for {title} below.\n-->\n")
            if not content:
                console.print("[bold red]Aborted:[/bold red] No content provided.")
                raise typer.Exit(code=1)
        else:
            # Implement AI-powered story generation
            content = "AI-generated story content." # Replace with actual logic

        target_path = Path(f"{title}.md") # Or a better default location
        _ai_confirm_write(content, target_path, dry_run, write)
    except Exception as e:
        _handle_ai_error("new-story", e)
```

### commands/plan.py

#### MODIFY src/agent/commands/plan.py

- Remove the `--offline` flag from the `new-runbook` command.
- Add an `--offline` flag to the `new-runbook` command.
- Modify the command logic to use AI by default.
- Implement graceful degradation: if the AI service is unreachable, fall back to manual input using `$EDITOR`.
- Use the `_ai_confirm_write` utility function to handle preview and confirm logic.

```python
# src/agent/commands/plan.py
import typer
from agent.commands._ai_utils import _ai_confirm_write, _handle_ai_error
def new_runbook(
    title: str = typer.Option(..., help="Runbook title"),
    offline: bool = typer.Option(False, "--offline", help="Disable AI and use manual input"),
    write: bool = typer.Option(False, "--write", help="Write to file without prompting"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without writing"),
):
    try:
        if offline:
            # Implement manual input using $EDITOR via typer.edit()
            content = typer.edit(text=f"<!-- \nManual input required. \nPlease write your runbook for {title} below.\n-->\n")
            if not content:
                console.print("[bold red]Aborted:[/bold red] No content provided.")
                raise typer.Exit(code=1)
        else:
            # Implement AI-powered runbook generation
            content = "AI-generated runbook content." # Replace with actual logic

        target_path = Path(f"{title}.md") # Or a better default location
        _ai_confirm_write(content, target_path, dry_run, write)
    except Exception as e:
        _handle_ai_error("new-runbook", e)
```

### commands/journey.py

#### MODIFY src/agent/commands/journey.py

- Remove the `--offline` flag from the `journey new` command.
- Add an `--offline` flag to the `journey new` command.
- Modify the command logic to use AI by default.
- Implement graceful degradation: if the AI service is unreachable, fall back to manual input using `$EDITOR`.
- Use the `_ai_confirm_write` utility function to handle preview and confirm logic.

```python
# src/agent/commands/journey.py
import typer
from agent.commands._ai_utils import _ai_confirm_write, _handle_ai_error
def new(
    description: str = typer.Option(..., help="Journey description"),
    offline: bool = typer.Option(False, "--offline", help="Disable AI and use manual input"),
    write: bool = typer.Option(False, "--write", help="Write to file without prompting"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without writing"),
):
    try:
        if offline:
            # Implement manual input using $EDITOR via typer.edit()
            content = typer.edit(text=f"<!-- \nManual input required. \nPlease write your journey for {description} below.\n-->\n")
            if not content:
                console.print("[bold red]Aborted:[/bold red] No content provided.")
                raise typer.Exit(code=1)
        else:
            # Implement AI-powered journey generation
            content = "AI-generated journey content." # Replace with actual logic

        target_path = Path("journey.md") # Or a better default location
        _ai_confirm_write(content, target_path, dry_run, write)
    except Exception as e:
        _handle_ai_error("journey new", e)
```

### commands/check.py

#### MODIFY src/agent/commands/check.py

- Remove the `--offline` flag from the `preflight` and `impact` commands.
- Add an `--offline` flag to the `preflight` and `impact` commands.
- Modify the command logic to use AI by default.
- Implement graceful degradation: if the AI service is unreachable, print a user-friendly error message and exit cleanly.

```python
# src/agent/commands/check.py
import typer
from agent.commands._ai_utils import _handle_ai_error
def preflight(
    story_id: str = typer.Option(None, help="Story ID"),
    offline: bool = typer.Option(False, "--offline", help="Disable AI and use manual analysis"),
):
    """
    Runs a preflight check on the current codebase.
    """
    try:
        if offline:
            console.print("[bold blue]Skipping AI preflight analysis due to --offline flag.[/bold blue]")
            # Implement standard (non-AI) preflight logic here
        else:
            # Implement AI-powered preflight check
            console.print("[bold green]Running AI preflight analysis...[/bold green]")
            # Replace with actual AI call
    except Exception as e:
        _handle_ai_error("preflight", e)

def impact(
    story_id: str = typer.Option(None, help="Story ID"),
    offline: bool = typer.Option(False, "--offline", help="Disable AI and use manual analysis"),
):
    """
    Analyzes the impact of the current changes.
    """
    try:
        if offline:
            console.print("[bold blue]Skipping AI impact analysis due to --offline flag.[/bold blue]")
            # Implement standard (non-AI) impact analysis logic here
        else:
            # Implement AI-powered impact analysis
            console.print("[bold green]Running AI impact analysis...[/bold green]")
            # Replace with actual AI call
    except Exception as e:
        _handle_ai_error("impact", e)

```

### agent/cli.py

#### MODIFY src/agent/cli.py

- Add the `--offline`, `--write`, and `--dry-run` flags as global options to the CLI.

```python
# src/agent/cli.py
import typer
from agent.commands.onboard import app as onboard_app

app = typer.Typer()

@app.callback()
def cli(
    offline: bool = typer.Option(False, "--offline", help="Disable AI and use manual analysis"),
    write: bool = typer.Option(False, "--write", help="Write to file without prompting"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without writing"),
):
    """
    Agent CLI
    """
    pass
```

## Verification Plan

### Automated Tests

- [x] Test `--offline` explicitly bypasses AI generation and calls standard behavior for `new-story`.
- [x] Test network failure triggers `$EDITOR` fallback for `new-story` command.
- [x] Test network failure triggers clean exit for `preflight`.
- [x] Test `_ai_confirm_write()` with yes / no / all / skip.
- [x] Test `--offline` flag on `impact` command.
- [ ] Add unit tests to check graceful degradation with network failure.

### Manual Verification

- [x] Run `env -u VIRTUAL_ENV uv run agent new-story --offline INFRA-TEST` → verify it skips AI and opens editor.
- [x] Run `env -u VIRTUAL_ENV uv run agent preflight` with network disabled → verify clean error without traceback.
- [ ] Run `env -u VIRTUAL_ENV uv run agent pr` with `--write` and ensure the output is written to the expected file.
- [ ] Verify help text for `--offline`, `--write`, and `--dry-run` is standardized across all commands.

## Definition of Done

### Documentation

- [x] CHANGELOG.md updated
- [x] README.md updated (if applicable)
- [ ] API Documentation updated (if applicable)

### Observability

- [x] Logs are structured and free of PII
- [ ] Metrics added for new features

### Testing

- [x] Unit tests passed
- [x] Integration tests passed
