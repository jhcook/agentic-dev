<!-- Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0. -->

# NotebookLM Integration Guide

The agent integrates with [Google NotebookLM](https://notebooklm.google.com) via the Model Context Protocol (MCP) to enable the **Oracle Preflight Pattern** — synchronizing stories, runbooks, ADRs, and rules into a NotebookLM notebook for enhanced AI governance context.

## Configuration

Add the NotebookLM MCP server to your `.agent/etc/agent.yaml`:

```yaml
agent:
  mcp:
    servers:
      notebooklm:
        command: uv
        args:
          - tool
          - run
          - --from
          - notebooklm-mcp-server
          - notebooklm-mcp
```

### Prerequisites

1. **Install `uv`** — The MCP server runs via [`uv tool run`](https://docs.astral.sh/uv/).
2. **Google Account** — You must be logged into [notebooklm.google.com](https://notebooklm.google.com) in a local browser.

## Authentication

NotebookLM lacks a dedicated API, so authentication uses browser session cookies.

### Automatic Extraction (Recommended)

```bash
agent mcp auth notebooklm --auto
```

This will:
1. Display a GDPR consent prompt (type `y` to proceed).
2. Extract active session cookies from your local browser (Chrome, Edge, Firefox).
3. Store them securely in the OS-native Keychain via `SecretManager`.

### Manual File Import

1. Navigate to <https://notebooklm.google.com> and open DevTools → **Application** → **Cookies**.
2. Copy `SID`, `HSID`, and `SSID` values into a JSON file.
3. Run:

```bash
agent mcp auth notebooklm --file path/to/cookies.json
```

### Other Flags

| Flag | Description |
|---|---|
| `--no-auto-launch` | Print manual extraction instructions |
| `--clear-session` | Clear cached credentials |

## Sync Commands

### Automatic Sync

NotebookLM syncs automatically during `agent preflight`. It uploads:
- Stories, runbooks, and plans from `.agent/cache/`
- ADRs from `.agent/adrs/`
- Rules from `.agent/rules/`

Only modified files are synced (tracked by modification time).

### Manual Sync

```bash
agent sync notebooklm           # Sync modified files
agent sync notebooklm --reset   # Clear sync state, force fresh sync
agent sync notebooklm --flush   # Delete notebook and all local state
```

## Security

- **Cookies are equivalent to your Google Account credentials.** They are never stored in plain text.
- Cookies are encrypted and stored in the OS-native keychain via `SecretManager`.
- Automatic extraction requires explicit user consent (defaults to denial).
- File content is scrubbed of sensitive data before upload via `scrub_sensitive_data()`.

## Troubleshooting

| Problem | Solution |
|---|---|
| `browser-cookie3` extraction failure | Ensure you're logged into notebooklm.google.com. Fall back to `--file` method. |
| Authentication expired | Re-run `agent mcp auth notebooklm --auto` to refresh cookies. |
| Corrupted sync state | Run `agent sync notebooklm --reset` to clear internal state. |
| Stale sources | Run `agent sync notebooklm --flush` to delete and re-sync everything. |
| Secret manager errors | Check your master password or `AGENT_MASTER_KEY` env var. |

## Disabling NotebookLM

To skip NotebookLM sync entirely, remove the `notebooklm` entry from `agent.mcp.servers` in `.agent/etc/agent.yaml`. Preflight will show `ℹ️ NotebookLM sync not configured.` and continue normally.
