# AI-Powered CLI Commands

This document provides details about the AI-related commands in the CLI (`implement`, `match-story`, `new-runbook`, `pr`).

---

## `agent secret` — Secret Management

Manage encrypted secrets for API keys and credentials. Secrets are stored encrypted using AES-256-GCM in `.agent/secrets/`.

### Subcommands

| Command | Description |
|---------|-------------|
| `agent secret init` | Initialize secret management with master password |
| `agent secret set <service> <key>` | Store an encrypted secret |
| `agent secret get <service> <key>` | Retrieve a secret (masked by default) |
| `agent secret list [service]` | List all secrets (values masked) |
| `agent secret delete <service> <key>` | Delete a secret |
| `agent secret import <service>` | Import secrets from environment variables |
| `agent secret export <service>` | Export secrets as environment variables |
| `agent secret services` | List supported services and env var mappings |

### Supported Services

| Service | Keys | Environment Variables |
|---------|------|----------------------|
| `supabase` | `service_role_key`, `anon_key` | `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY` |
| `openai` | `api_key` | `OPENAI_API_KEY` |
| `gemini` | `api_key` | `GEMINI_API_KEY`, `GOOGLE_GEMINI_API_KEY` |
| `anthropic` | `api_key` | `ANTHROPIC_API_KEY` |
| `gh` | `api_key` | `GH_API_KEY`, `GITHUB_TOKEN` |

### Usage Examples

```bash
# Initialize (first time only)
agent secret init

# Import API keys from environment variables
agent secret import openai
agent secret import supabase

# Set a secret manually
agent secret set openai api_key --value sk-xxx

# List all secrets
agent secret list

# Get a secret (masked)
agent secret get openai api_key

# Get a secret (revealed)
agent secret get openai api_key --show

# Export for CI/CD
agent secret export supabase > .env.local
```

### Security

- **Encryption**: AES-256-GCM with PBKDF2 key derivation (100k iterations)
- **File Permissions**: 600 (owner read/write only)
- **Gitignore**: `.agent/secrets/` is automatically gitignored
- **Backward Compatibility**: Falls back to environment variables if secrets not configured

See [ADR-006](../adrs/ADR-006-encrypted-secret-management.md) for architecture details.

---

## `--provider` Option

### Purpose
The `--provider` option allows developers to select an AI provider (`gh`, `gemini`, `openai`) explicitly. This enables flexibility while ensuring the proper provider is configured before use.

### Accepted Values
- `gh` (default)
- `gemini`
- `openai`

### Default Behavior
If the `--provider` flag is omitted, the system defaults to the `gh` provider, assuming it is correctly configured. If `gh` is not configured, the system will raise a `RuntimeError`.

### Configuration Prerequisites
To use an AI provider, the appropriate environment variables or configuration keys must be set:

- **`gh`**: Requires appropriate GitHub access configuration (if any).
- **`gemini`**: Requires `GEMINI_API_KEY` environment variable or configuration setting.
- **`openai`**: Requires `OPENAI_API_KEY` to be set in the environment or configuration.

For example: