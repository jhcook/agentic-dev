# STORY-ID: INFRA-045: Restore Agent Sync Functionality

## State

ACCEPTED

## Goal Description

Restore the functionality of the `agent sync` command and its subcommands (`pull`, `push`, `scan`, `status`) by correcting the CLI entry point, removing the broken `agent.sync.main` module, and ensuring proper authentication for sensitive operations.

## Panel Review Findings

- **@Architect**: Verified structure. Moving `with_creds` to `agent.core.auth.decorators` avoids circular imports and promotes reuse.
- **@Security**: `pull` and `push` connect to remote backend (Supabase). Enforcing `with_creds` is mandatory to prevent unauthorized access errors and ensure a valid session token exists.
- **@QA**: Manual smoke tests and `tests/smoke_sync.sh` are sufficient for this structural fix.
- **@Product**: Improved status messages will help developers trust the sync state.

## Implementation Steps

### agent

#### NEW src/agent/core/auth/decorators.py

- Extract `with_creds` decorator from `main.py` into this new file to allow reuse in `sync/cli.py` without circular imports.

```python
from functools import wraps
import typer
from agent.core.auth.credentials import validate_credentials
from agent.core.auth.errors import MissingCredentialsError

def with_creds(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            validate_credentials()
        except MissingCredentialsError as e:
            print(e)
            raise typer.Exit(code=1)
        return func(*args, **kwargs)
    return wrapper
```

#### MODIFY src/agent/main.py

- Remove the inline `with_creds` definition.
- Import `with_creds` from `agent.core.auth.decorators`.
- Update the `sync` command wiring to use `app.add_typer`.

```python
# ... imports
from agent.core.auth.decorators import with_creds

# ... (remove inline with_creds)

# ...

# OLD:
# @app.command(name="sync")
# def sync_cmd(cursor: str = None):
#    ...

# NEW:
from agent.sync import cli as sync_cli
app.add_typer(sync_cli.app, name="sync")
```

#### MODIFY src/agent/sync/cli.py

- Import `with_creds`.
- Decorate `pull` and `push`.
- **CRITICAL**: Preserve existing logic calling `sync_ops`.

```python
import typer
from agent.sync import sync as sync_ops
from agent.core.auth.decorators import with_creds  # [NEW]

# ...

@app.command()
@with_creds  # [NEW]
def pull(verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output")):
    """Pull artifacts from remote."""
    sync_ops.pull(verbose=verbose)

@app.command()
@with_creds  # [NEW]
def push(verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output")):
    """Push artifacts to remote."""
    sync_ops.push(verbose=verbose)

# ...
```

#### DELETE src/agent/sync/main.py

- Remove this broken file.

#### NEW tests/smoke_sync.sh

- Create a script to verify the CLI wiring.

```bash
#!/bin/bash
set -e

echo "Running agent sync smoke tests..."

# 1. Check help
agent sync --help > /dev/null
echo "✅ agent sync --help passed"

# 2. Check status (assuming it doesn't need auth, or if it does, ensure creds are present or it fails gracefully)
# agent sync status

echo "Global sync smoke test passed."
```

- Make executable: `chmod +x tests/smoke_sync.sh`

## Verification Plan

### Automated Tests

- [ ] Run `tests/smoke_sync.sh`.

### Manual Verification

1. **Help**: `agent sync --help` shows subcommands.
2. **Status**: `agent sync status` shows output.
3. **Auth**:
   - Rename `~/.agent/credentials` momentarily.
   - Run `agent sync pull`.
   - Expect error: "Missing Credentials..."
   - Restore credentials.
4. **Success**: `agent sync pull` works (or attempts connection).

## Definition of Done

- `agent sync` subcommands are wired correctly.
- `pull`/`push` are protected by `with_creds`.
- Broken file deleted.
