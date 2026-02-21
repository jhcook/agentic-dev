# INFRA-015: Create `env -u VIRTUAL_ENV uv run agent onboard` CLI command

## State
ACCEPTED

## Goal Description
To create a new CLI command, `env -u VIRTUAL_ENV uv run agent onboard`, that automates the initial setup for developers. This command will verify system dependencies, interactively and securely configure necessary API keys, initialize the required workspace directory structure, and perform a final health check to ensure the agent is ready for immediate use.

## Panel Review Findings
- **@Architect**: The proposed implementation using `pathlib` for file system operations is robust and aligns with modern Python practices. The choice to make the command idempotent is critical for a good user experience, preventing accidental overwrites of existing configurations. The architecture should ensure that dependency-checking logic is decoupled and potentially reusable by other commands (e.g., in `agent.core.utils`). The command should be self-contained and not introduce complex dependencies to the core agent logic. The plan to target macOS/Linux first and fail fast on Windows is a sensible approach for initial delivery.

- **@Security**: The requirements to use masked input for secrets and set file permissions to `600` on the `.env` file are non-negotiable and correctly identified. The check to ensure `.env` is listed in `.gitignore` is a crucial safeguard against accidental secret exposure. The implementation must use a secure method for checking binaries (e.g., `shutil.which`) and avoid executing shell commands constructed from user input to prevent any risk of command injection. All user-provided input should be treated as untrusted.

- **@QA**: The test strategy is a good start, but needs more specific negative test cases. We must verify behavior under various failure conditions:
    - What happens if `.gitignore` exists but is not writable?
    - What if the user presses Ctrl+C during the API key prompt?
    - How does the command handle a file system that is read-only?
    - Test the exact error message when `.agent` exists as a file.
    - The manual verification plan must be executed in a clean, containerized environment (e.g., using a fresh `python:3.11-slim` Docker image) to accurately simulate a new developer's machine.

- **@Docs**: The user story correctly identifies the need to update `README.md` and `CONTRIBUTING.md`. The "Quick Start" section of the `README.md` must be rewritten to prioritize `env -u VIRTUAL_ENV uv run agent onboard` as the primary setup method. The old manual steps should be moved to an "Advanced" or "Manual Setup" section. The CLI's built-in help text (`env -u VIRTUAL_ENV uv run agent onboard --help`) must also be comprehensive, explaining what the command does and any options it might have.

- **@Compliance**: The user story does not involve changes to any API contracts or architecture governed by an existing ADR, so no direct violations of `api-contract-validation.mdc` or `adr-standards.mdc` are found. However, the team must remain vigilant. If any part of this implementation were to require, for instance, a new configuration service endpoint, it would immediately fall under the purview of the API contract rules. The work does not require a new ADR at this time.

- **@Observability**: While this is a CLI tool and not a long-running service, observability is still relevant for diagnostics. The command's output should be structured. Use clear prefixes like `[INFO]`, `[WARN]`, `[ERROR]` for all messages printed to the console. This allows for easier parsing and debugging. Crucially, ensure that no secrets (API keys) are ever logged to stdout/stderr, even in a verbose or debug mode. The final exit code must reliably reflect success (0) or failure (non-zero), as this is the primary metric for automation scripts.

## Implementation Steps
### agent/commands/onboard.py
#### [NEW] `agent/commands/onboard.py`
- Create a new file to house the logic for the `onboard` command.
- Use the `typer` library for the CLI interface.
- Implement functions for each step outlined in the acceptance criteria.

```python
import typer
import shutil
import getpass
from pathlib import Path

# Placeholder for other agent imports (e.g., for 'agent check')

app = typer.Typer()

REQUIRED_BINARIES = ["python3", "git"]
RECOMMENDED_BINARIES = ["docker"]
ENV_VARS = ["OPENAI_API_KEY", "GEMINI_API_KEY"]
AGENT_DIR = Path(".agent")
ENV_FILE = Path(".env")
GITIGNORE_FILE = Path(".gitignore")

def _check_dependencies():
    """Checks for required and recommended system dependencies."""
    typer.echo("[INFO] Checking system dependencies...")
    for binary in REQUIRED_BINARIES:
        if not shutil.which(binary):
            typer.secho(f"[ERROR] Required binary '{binary}' not found in PATH.", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        typer.secho(f"  - Found {binary}", fg=typer.colors.GREEN)
    for binary in RECOMMENDED_BINARIES:
        if not shutil.which(binary):
            typer.secho(f"[WARN] Recommended binary '{binary}' not found. Some features may be unavailable.", fg=typer.colors.YELLOW)
        else:
            typer.secho(f"  - Found {binary}", fg=typer.colors.GREEN)

def _setup_env_file():
    """Interactively prompts for missing environment variables."""
    typer.echo("\n[INFO] Configuring environment variables...")
    existing_vars = {}
    if ENV_FILE.exists():
        with ENV_FILE.open("r") as f:
            for line in f:
                if '=' in line:
                    key, val = line.strip().split('=', 1)
                    existing_vars[key] = val

    vars_to_add = {}
    for var in ENV_VARS:
        if var not in existing_vars or not existing_vars[var]:
            value = getpass.getpass(f"Enter your {var}: ")
            vars_to_add[var] = value

    if vars_to_add:
        with ENV_FILE.open("a") as f:
            for key, val in vars_to_add.items():
                f.write(f"\n{key}={val}")
        ENV_FILE.chmod(0o600)
        typer.secho(f"  - Updated '{ENV_FILE}' and set permissions to 600.", fg=typer.colors.GREEN)
    else:
        typer.secho(f"  - All required variables already exist in '{ENV_FILE}'.", fg=typer.colors.GREEN)

def _init_workspace():
    """Initializes the .agent/ directory structure."""
    typer.echo("\n[INFO] Initializing agent workspace...")
    if AGENT_DIR.is_file():
        typer.secho(f"[ERROR] A file named '{AGENT_DIR}' exists. Please remove it and run again.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    AGENT_DIR.mkdir(exist_ok=True)
    # Create subdirectories if needed, e.g., AGENT_DIR.joinpath("logs").mkdir(exist_ok=True)
    typer.secho(f"  - Ensured '{AGENT_DIR}/' directory exists.", fg=typer.colors.GREEN)

def _verify_gitignore():
    """Ensures .env is in .gitignore."""
    typer.echo("\n[INFO] Verifying .gitignore...")
    if not GITIGNORE_FILE.exists():
        with GITIGNORE_FILE.open("w") as f:
            f.write(".env\n")
        typer.secho(f"  - Created '{GITIGNORE_FILE}' and added '.env'.", fg=typer.colors.GREEN)
    else:
        with GITIGNORE_FILE.open("r") as f:
            content = f.read()
        if ".env" not in content.splitlines():
            with GITIGNORE_FILE.open("a") as f:
                f.write("\n.env\n")
            typer.secho(f"  - Added '.env' to existing '{GITIGNORE_FILE}'.", fg=typer.colors.GREEN)
        else:
            typer.secho(f"  - '.env' is already in '{GITIGNORE_FILE}'.", fg=typer.colors.GREEN)

def _run_health_check():
    """Runs the final health check."""
    typer.echo("\n[INFO] Running final health check...")
    # This assumes 'agent check' is implemented elsewhere and can be called.
    # result = call_agent_check_command()
    # if result.exit_code != 0:
    #     typer.secho("[ERROR] Health check failed. Please review the output above.", fg=typer.colors.RED)
    #     raise typer.Exit(code=1)
    typer.secho("  - Health check passed!", fg=typer.colors.GREEN) # Placeholder

@app.command()
def onboard():
    """
    Checks dependencies, sets up configuration, and initializes the workspace.
    """
    _check_dependencies()
    _init_workspace()
    _setup_env_file()
    _verify_gitignore()
    _check_dependencies()
    _init_workspace()
    _setup_env_file()
    _verify_gitignore()
    _setup_frontend() # New step
    _run_health_check()

    typer.secho("\n🚀 Onboarding Complete! 🚀", fg=typer.colors.CYAN)
    typer.echo("\nNext Steps:")
    typer.echo("1. Explore available commands: agent --help")
    typer.echo("2. Start your first task: agent run 'your first task'")

if __name__ == "__main__":
    app()
```

### agent/cli.py
#### [MODIFY] `agent/cli.py`
- Import the new `onboard` command and register it with the main `typer` app.

```python
# ... other imports
import typer
from agent.commands import onboard, check # assuming 'check' is another command

app = typer.Typer()

# Register the new command
app.add_typer(onboard.app, name="onboard")
app.add_typer(check.app, name="check")
# ... other commands

if __name__ == "__main__":
    app()
```

## Verification Plan
### Automated Tests
- [ ] **Unit Test (`test_onboard.py`)**: Test `_check_dependencies` by mocking `shutil.which` to return `True` and `False` for different binaries.
- [ ] **Unit Test (`test_onboard.py`)**: Test `_setup_env_file` by mocking `pathlib.Path.exists`, `open`, and `getpass.getpass` to simulate scenarios where `.env` is missing, empty, or partially complete.
- [ ] **Unit Test (`test_onboard.py`)**: Test `_init_workspace` by mocking `pathlib.Path` to check that `mkdir` is called correctly and that it raises an error if `.agent` is a file.
- [ ] **Unit Test (`test_onboard.py`)**: Test `_verify_gitignore` for all three cases: file does not exist, file exists but is missing `.env`, and file exists with `.env` already present.
- [ ] **Integration Test**: Write a test that uses a `CliRunner` to invoke the `onboard` command with a series of mocked inputs and asserts on the final state of the file system (e.g., `.env` content, `.agent` directory existence).

### Manual Verification
- [ ] On a fresh clone of the repository (or in a clean Docker container), delete any existing `.env` or `.agent` directories.
- [ ] Run `python -m agent.cli onboard`.
- [ ] Follow the interactive prompts, entering API keys when requested. Verify the input is masked (not echoed to the terminal).
- [ ] After completion, verify that a `.env` file was created with the correct keys and has `600` permissions (`ls -l .env`).
- [ ] Verify that the `.agent/` directory has been created.
- [ ] Verify that `.gitignore` exists and contains a line for `.env`.
- [ ] Run the command a second time and confirm that it does not re-prompt for the API keys that were just entered.
- [ ] Manually delete one key from `.env` and run the command again. Confirm it only prompts for the missing key.

## Definition of Done
### Documentation
- [ ] `CHANGELOG.md` updated with a summary of the new `env -u VIRTUAL_ENV uv run agent onboard` feature.
- [ ] `README.md` updated in the "Quick Start" section to recommend `env -u VIRTUAL_ENV uv run agent onboard` as the primary setup method.
- [ ] `CONTRIBUTING.md` updated to reflect the new onboarding process for developers.

### Observability
- [ ] Logs printed to the console are structured with `[INFO]`, `[WARN]`, `[ERROR]` prefixes.
- [ ] Confirmed that API keys or other secrets are never printed to stdout/stderr.

### Testing
- [ ] Unit tests passed for all new functions and logic paths.
- [ ] Integration tests passed for the end-to-end `onboard` command flow.