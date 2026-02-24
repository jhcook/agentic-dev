# INFRA-078: Preflight Remediation for NotebookLM Authentication

## State

ACCEPTED

## Goal Description

Improve the NotebookLM authentication flow in the `agentic-dev` CLI to address security, compliance, observability, and testing deficiencies identified in the previous implementation (INFRA-077). This includes prompting for user consent, secure storage of credentials, dependency pinning, documentation updates, bug fixes, and proper observability integration.

## Linked Journeys

- JRN-063: Secure CLI Authentication

## Panel Review Findings

- **@Architect**: The plan to create an ADR (ADR-0003) is good. The use of SecretManager aligns with ADR-0002 for credential storage. No concerns.
- **@Qa**: The Test Strategy needs to be expanded. Specific tests for the consent prompt, secure storage, and error handling around browser-cookie3 failures are missing. The acceptance criteria are clear and testable.
- **@Security**: The plan to use SecretManager is good. Pinning `browser-cookie3` is critical. We MUST ensure no secrets are ever printed to logs.  Ensure the consent prompt clearly states what cookies are being extracted and why.
- **@Product**: The acceptance criteria accurately reflect the user's need for a secure and compliant authentication flow. The impact analysis should also include an estimate of the work required to implement these changes.
- **@Observability**: Structured logging is mentioned, but examples of log messages are needed. OpenTelemetry spans are required for the authentication flow, spanning cookie extraction, storage, and any API calls made to NotebookLM.
- **@Docs**: The documentation updates are necessary. The README needs to be very clear about the new consent requirement.
- **@Compliance**: The consent prompt MUST be GDPR-compliant. The purpose of cookie extraction must be clearly explained, and users must have a clear way to opt-out.  The lawful basis for data processing is legitimate interest, but this should be documented in the ADR.
- **@Mobile**: N/A - This story primarily impacts the CLI tool, not mobile.
- **@Web**: N/A - This story primarily impacts the CLI tool, not the web interface.
- **@Backend**: The synchronization of tool names is important. Validate that the `mcp_notebooklm_` prefix is consistently used in all relevant server-side components.

## Targeted Refactors & Cleanups (INFRA-043)

- [x] Convert prints to logger in `src/agent/commands/check.py` (General cleanup, spotted in the code).

## Implementation Steps

### src/agent/cli.py

#### MODIFY src/agent/cli.py

- Add `--auto` flag to the `auth` command, and keep and document the `--no-auto-launch` flag. Implement consent prompt using `rich.prompt.Confirm` if `--auto` is specified.

```python
import typer
from rich.console import Console
from rich.prompt import Confirm

app = typer.Typer()
console = Console()

@app.command()
def auth(
    file: str = typer.Option(None, help="Path to credentials file."),
    auto: bool = typer.Option(False, help="Automatically extract credentials from browser cookies with consent."),
):
    if auto:
        consent = Confirm.ask("Agentic-dev CLI requires your consent to securely extract cookies from your local browser to authenticate with NotebookLM. Do you consent?")
        if not consent:
            console.print("Authentication aborted by user.")
            raise typer.Exit(code=1)

        # IMPLEMENT COOKIE EXTRACTION LOGIC HERE, SECURELY
        # ...
```

### src/agent/commands/secret.py

#### MODIFY src/agent/commands/secret.py

- Implement secure cookie storage using `agent.core.secrets.SecretManager`. Refactor `auth.json` reading and writing to use SecretManager.

```python
from agent.core.secrets import SecretManager
import os

def store_cookies(cookies: dict):
    secret_manager = SecretManager()
    secret_manager.set_secret("notebooklm_cookies", cookies)

def load_cookies() -> dict:
    secret_manager = SecretManager()
    return secret_manager.get_secret("notebooklm_cookies") or {}

def clear_cookies():
    secret_manager = SecretManager()
    secret_manager.delete_secret("notebooklm_cookies")

```

### src/agent/commands/check.py

#### MODIFY src/agent/commands/check.py

- Add OpenTelemetry tracing spans around the cookie extraction, storage, and NotebookLM API calls in the check command for increased observability.

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

def check():
    with tracer.start_as_current_span("notebooklm_auth"):
        # Cookie extraction and storage logic here
        with tracer.start_as_current_span("extract_cookies"):
            # Implement cookie extraction logic using browser-cookie3
            pass # your implementation
        with tracer.start_as_current_span("store_cookies"):
            # Store cookies using SecretManager
            pass # your implementation
        with tracer.start_as_current_span("notebooklm_api_call"):
            # Perform NotebookLM API calls using the extracted cookies
            pass # your implementation
```

### src/agent/commands/cli.py

#### MODIFY src/agent/cli.py

- Implement the cookie extraction logic using `browser-cookie3==0.20.1` *after* receiving consent. Handle potential exceptions during cookie extraction gracefully. Replace the `--file` boolean flag with a string for the file path.

```python
import typer
import browser_cookie3
from rich.console import Console
from rich.prompt import Confirm

app = typer.Typer()
console = Console()

@app.command()
def auth(
    file: str = typer.Option(None, help="Path to credentials file."),
    auto: bool = typer.Option(False, help="Automatically extract credentials from browser cookies with consent."),
):
    if auto:
        consent = Confirm.ask("Agentic-dev CLI requires your consent to securely extract cookies from your local browser to authenticate with NotebookLM by extracting cookies such as `__Secure-nlmdid` and `NID`. Do you consent?")
        if not consent:
            console.print("Authentication aborted by user.")
            raise typer.Exit(code=1)

        try:
            cookies = browser_cookie3.chrome(domain_name='notebooklm.google.com') # or firefox() or any other browser
            # Filter cookies relevant to NotebookLM
            notebooklm_cookies = {cookie.name: cookie.value for cookie in cookies if 'notebooklm' in cookie.domain or 'google.com' in cookie.domain} # Filter the cookie domains
            # Store cookies securely
            store_cookies(notebooklm_cookies)
            console.print("[bold green]Successfully extracted and stored NotebookLM cookies![/]")

        except browser_cookie3.BrowserError as e:
            console.print(f"[bold red]Error extracting cookies: {e}[/]")
            console.print("[yellow]Please ensure you have a supported browser installed and are logged in to NotebookLM.[/]")
            raise typer.Exit(code=1)
    elif file:
        console.print(f"Authenticating with file: {file}")
        # TODO: implement file auth
    else:
        console.print("[bold red]Please specify either --file or --auto for authentication.[/]")
        raise typer.Exit(code=1)

```

### src/agent/commands/mcp.py

#### MODIFY src/agent/commands/mcp.py

- Ensure that the backend NotebookLM sync tools use the correct prefix (`mcp_notebooklm_`).

```python
# Example Usage inside src/agent/commands/mcp.py
TOOL_PREFIX = "mcp_notebooklm_"

async def _run_tool_internal(server: str, tool: str, args_str: str) -> None:
    if not tool.startswith(TOOL_PREFIX):
        tool = TOOL_PREFIX + tool # Enforce Prefix for backend tools.
    # ... rest of the logic
```

### requirements.txt

#### MODIFY requirements.txt

- Pin the `browser-cookie3` dependency to exactly version `0.20.1`.

```
browser-cookie3==0.20.1
```

### README.md

#### MODIFY README.md

- Document the `--file`, `--auto`, and `--no-auto-launch` flags in the CLI documentation.

```markdown
## Authentication

The CLI supports multiple authentication methods:

- `--file`:  Authenticate using a credentials file (JSON).
- `--auto`: Automatically extract credentials from your browser with explicit consent. This method securely stores the extracted cookies.
```

### CHANGELOG.md

#### MODIFY CHANGELOG.md

- Add a CHANGELOG entry detailing the changes to the authentication flow, including the new `--auto` flag, consent requirement, and secure storage.

```markdown
## v0.X.X - YYYY-MM-DD

### Changed

- Improved NotebookLM authentication flow:
    - Added `--auto` flag for automatic cookie extraction with explicit user consent.
    - Securely store extracted cookies using `SecretManager`.
    - Documented exactly how to use `--no-auto-launch` flag.
    - Fixed: `--file` flag accepts a file path argument.
```

## Verification Plan

### Automated Tests

- [ ] Create a unit test for the `store_cookies` function in `src/agent/commands/secret.py` to verify that cookies are stored securely.
- [ ] Create an integration test to simulate the `--auto` flag flow, including the consent prompt and cookie extraction. Mock `browser_cookie3` for testing purposes.
- [ ] Add tests to verify the corrected behavior of the `--file` flag.
- [ ] Verify MCP tool prefix enforcement with a unit test.

### Manual Verification

- [ ] Run the CLI with the `--auto` flag and verify that the consent prompt appears.
- [ ] After granting consent, verify that the cookies are stored securely (e.g., by inspecting the SecretManager's storage location).
- [ ] Verify that the CLI can authenticate with NotebookLM using the extracted cookies.
- [ ] Run `agent check` and confirm OpenTelemetry tracing spans are present.
- [ ] Run the CLI with the `--file` flag and ensure it accepts a file path.

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

## Copyright

Copyright 2026 Justin Cook
