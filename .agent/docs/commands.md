# AI-Powered CLI Commands

This document provides details about the AI-related commands in the CLI (`implement`, `match-story`, `new-runbook`, `pr`).

---

## Global Options

The `agent` CLI supports the following global options across all commands:

| Option | Shorthand | Description |
|--------|-----------|-------------|
| `--verbose` | `-v` | **INFO**: Show high-level agent logs. |
| (repeat) | `-vv` | **DEBUG**: Show detailed agent logs (libraries silenced). |
| (repeat) | `-vvv` | **TRACE**: Show all logs (including libraries like `httpx`). |
| `--help` | | Show help message and exit. |

## `agent audit` — Governance Audit

Execute a comprehensive governance audit of the repository to ensure traceability, identify stagnant code, and flag orphaned artifacts.

### Usage

```bash
# Run audit (fails if score < 80%)
agent audit

# Run audit with strict failure on ANY error
agent audit --fail-on-error

# Custom traceability threshold
agent audit --min-traceability 90

# Output report to custom file
agent audit --output reports/audit-Q1.md
```

### Options

| Option | Description |
|--------|-------------|
| `--fail-on-error` | Exit with non-zero code if *any* governance issues are found. |
| `--min-traceability <int>` | Minimum % of files that must be governed (Default: 80). |
| `--stagnant-months <int>` | Months before un-governed code is considered stagnant (Default: 6). |
| `--output <path>` | Path to save the Markdown report. |

### Configuration

- **`.auditignore`**: Add file patterns here to exclude them from the audit (e.g. `legacy/**`).
- **`.gitignore`**: Files ignored by git are automatically excluded.

---

## `agent sync` — Artifact Synchronization

Synchronize artifacts (stories, plans, runbooks) between your local cache and the remote Supabase backend.

### Subcommands

| Command | Description |
|---------|-------------|
| `agent sync pull` | Pull artifacts from remote to local cache |
| `agent sync push` | Push local artifacts to remote |
| `agent sync status` | View local cache inventory |
| `agent sync delete` | Delete artifacts from local cache |
| `agent sync scan` | Scan local filesystem and populate cache |
| `agent sync janitor` | Maintain relational integrity (e.g. Notion linking) |
| `agent sync init` | Bootstrap sync environments (e.g. create Notion databases) |

### Options

| Option | Description |
|--------|-------------|
| `--backend <name>` | Specific backend to use (e.g. `notion`). Default: All. |
| `--force` | Force overwrite without interactive prompts. |

### Usage Examples

```bash
# Pull latest changes (from all backends)
agent sync pull

# Pull only from Notion
agent sync pull --backend notion

# Push to Notion (overwriting remote if conflict)
agent sync push --backend notion --force

# Run Janitor for Notion
agent sync janitor --backend notion

# Initialize/Bootstrap Notion environment
agent sync init --backend notion

# View status
agent sync status
agent sync status --detailed
```

---

## `agent secret` — Secret Management

Manage encrypted secrets for API keys and credentials. Secrets are stored encrypted using AES-256-GCM in `.agent/secrets/`.

### Subcommands

| Command | Description |
|---------|-------------|
| `agent secret init` | Initialize secret management with master password |
| `agent secret login` | Securely store master password in System Keychain |
| `agent secret logout` | Remove master password from System Keychain |
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

# 1. Store Master Password in Keychain (Recommended)
agent secret login

# 2. Import API keys from environment variables
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
- **Required for AI Commands**: If secrets are initialized, you **must** run `agent secret login` before using AI commands. The agent will not fall back to environment variables if secrets are locked.

See [ADR-006](../adrs/ADR-006-encrypted-secret-management.md) for architecture details.

---

## `agent impact` — Impact Analysis

Run impact analysis for a story to identify risks and affected components.

### Usage

```bash
# Static analysis (default)
agent impact STORY-001

# AI-powered analysis (risk assessment, breaking changes)
agent impact STORY-001 --ai

# Update the story file with the analysis
agent impact STORY-001 --ai --update-story
```

### Options

| Option | Description |
|--------|-------------|
| `--ai` | Enable AI-powered analysis (requires API key) |
| `--update-story` | Write the analysis to the "Impact Analysis Summary" section of the story file |
| `--base <branch>` | Compare against a specific branch (default: staged changes) |
| `--provider <name>` | Force AI provider (gh, gemini, openai) |

---

## `agent list-models` — AI Model Discovery

List available AI models from configured providers to verify connectivity and availability.

### Usage

```bash
# List models from default provider
agent list-models

# List models from specific provider
agent list-models gemini
agent list-models openai
agent list-models anthropic

# Output in JSON format
agent list-models gemini --format json
```

### Options

| Option | Description |
|--------|-------------|
| `--format <format>` | Output format: pretty, json, csv, yaml, markdown, plain, tsv |
| `--output <file>` | Write output to file instead of stdout |

---

## `agent admin` — Agent Management Console

Manage the visual dashboard for the agent system, launching both the backend API and frontend UI.

### Usage

```bash
# Start in background (Default)
agent admin start

# Start and follow logs
agent admin start --follow

# Check status
agent admin status

# Stop services
agent admin stop
```

### Architecture

- **Backend**: FastAPI running on `localhost:8000`.
- **Frontend**: Vite/React running on `localhost:8080`.
- **Proxy**: The frontend proxies `/api` requests to the backend.
- **Source**: Frontend code is located in `.agent/web/`.

---

## `agent run-ui-tests` — Mobile UI Testing

Execute UI journey tests using [Maestro](https://maestro.mobile.dev/).

### Usage

```bash
# Run all UI tests
agent run-ui-tests

# Filter specific flows
agent run-ui-tests --filter "login"
```

---

## `agent workflow` — Agentic Workflows

The CLI provides commands to drive the Agentic Workflow (Stories -> Plans -> Runbooks -> Implementation).

### Commands

| Command | Description |
|---------|-------------|
| `agent new-story [ID]` | Create a new user story (interactive). |
| `agent new-runbook <STORY_ID>` | Generate an implementation runbook for a committed story. |
| `agent implement <RUNBOOK_ID>` | Implement a feature from an accepted runbook. |
| `agent pr` | Create a Pull Request with automated preflight checks (displays blocking reasons on failure). |
| `agent commit` | Commit changes using conventional commits (optionally with `--ai`). |

### Usage Examples

```bash
# 1. Create a Story
agent new-story WEB-101

# 2. Planning (Create Runbook)
agent new-runbook WEB-101

# 3. Implementation
agent implement WEB-101

# 4. Create PR
agent pr --story WEB-101
```

---

## `--provider` Option

### Purpose

The `--provider` option allows developers to select an AI provider (`gh`, `gemini`, `openai`) explicitly. This enables flexibility while ensuring the proper provider is configured before use.

### Accepted Values

- `gh` (default)
- `gemini`
- `openai`
- `anthropic`

### Default Behavior

If the `--provider` flag is omitted, the system defaults to the `gh` provider, assuming it is correctly configured. If `gh` is not configured, the system will raise a `RuntimeError`.

### Configuration Prerequisites

To use an AI provider, the appropriate environment variables or configuration keys must be set:

- **`gh`**: Requires appropriate GitHub access configuration (if any).
- **`gemini`**: Requires `GEMINI_API_KEY` environment variable or configuration setting.
- **`openai`**: Requires `OPENAI_API_KEY` to be set in the environment or configuration.
- **`anthropic`**: Requires `ANTHROPIC_API_KEY` to be set in the environment or configuration.

For example:

### agent preflight

Run governance checks, automated tests, and linting on your current changes.

```bash
agent preflight [OPTIONS]
```

#### Options

- `--story [ID]`: Link the preflight check to a specific Story ID (e.g., `WEB-001`).
- `--interactive`: **[NEW]** Enable interactive repair mode. The agent will propose fixes for failures.
- `--ai`: Enable AI-powered governance review (requires API key).
- `--base [BRANCH]`: Verify changes against a specific base branch (default: staged vs HEAD).
- `--skip-tests`: Skip automated tests.

### Voice Agent Integration

When running in Voice Mode (triggered by `AGENT_VOICE_MODE=1` or via the Voice Agent), the preflight command optimizes its output for Text-to-Speech (TTS):

- **Formatted Output**: Uses clear, concise summaries instead of raw logs.
- **Interactive Repair**: The `--interactive` flag allows the agent to propose fixes, which the user can accept/reject via voice commands (mapped to keyboard input).

#### Voice Commands Reference

| Command | Action |
| :--- | :--- |
| "Option One" | Select Fix Option 1 |
| "Yes" | Confirm Action |
| "No" | Cancel Action |
| "Quit" | Exit Preflight |

### Compliance & Data Safety

The Agentic Development Tool utilizes AI for code analysis and repair. To ensure compliance with data protection standards (GDPR/SOC2):

- **Lawful Basis**: Processing is based on **Legitimate Interest** (development efficiency) and **User Consent** (explicit invocation of `--ai` flag).
- **Data Retention**: All AI context (lines of code, story content) is **ephemeral**. It is sent to the provider for inference and discarded immediately after the session. No code is stored by the AI provider for model training (via Enterprise agreements).
- **Human-in-the-Loop**: All AI-generated fixes must be explicitly reviewed and confirmed by the user before being applied to the filesystem. The agent **never** auto-commits changes without user verified approval.
- **Monitoring**: Logs are kept locally in `.agent/logs/` for security auditing but are not stripped of PII unless explicitly tagged. Users are responsible for not committing PII.

- **Constraints**:
  - Users must speak clearly when selecting options (e.g., "Option one", "Yes", "No").
  - Complex diffs are summarized to avoid reading thousands of lines of code.

Example Voice Flow:

1. User: "Run preflight check on story INFRA-042."
2. Agent: "Running checks... I found a schema error. Should I fix it?"
3. User: "Yes, please."
4. Agent: "Fix applied. Verifying... All checks passed."
