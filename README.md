# Agent

## 🚀 Interactive Preflight

The `agent preflight` command now supports an interactive mode to help you resolve issues faster.

```bash
agent preflight --story WEB-001 --ai --interactive
```

If validation fails (e.g. schema errors or governance blocks), the agent will:

1. **Explain the issue** clearly.
2. **Propose fixes** using AI.
3. **Apply the fix** automatically upon your approval.
4. **Offer manual fallback** if AI generation fails.

Here is the updated content:
This is powered by the `InteractiveFixer` and supports both Schema Validation and Governance Policy checks.

### 🎙️ Voice Mode

The interactive preflight tool is fully integrated with the **Voice Agent**. When running via the voice interface:

- **Output is optimized for speech**: Long lists are summarized, and options are read out clearly.
- **Hands-free control**: You can select options by saying "Option One" or "Fix it".
- **Auto-detection**: The agent automatically detects voice sessions via the `AGENT_VOICE_MODE` environment variable.

To test voice mode behavior in your terminal without the voice client:

```bash
export AGENT_VOICE_MODE=1
agent preflight --interactive
```

## Troubleshooting: Missing Credentials

The agent requires credentials for certain commands that interact with AI providers (e.g., OpenAI, Anthropic, Gemini). If you encounter an error message like:

`[❌ Missing Credentials] The following required credentials are not found: - OPENAI_API_KEY`

It means you are trying to use an AI feature (e.g., `--ai`) without valid credentials. Credentials are **optional** for core commands and only required when utilizing AI capabilities.

### Prerequisites

- **Python 3.10+** (Managed via `.venv` or system)
- **Git**
- **GitHub CLI (`gh`)**: For AI model access and PR management.
- **Node.js & npm** (Optional but Recommended): Required for `web` development and advanced linting (`markdownlint`).
  - The CLI uses `npx` to run linters without polluting your global scope.

### Installation

#### 1. Checking Your Configuration

First, check which AI provider you are trying to use. The default is `openai`. You can check or set the provider using the `LLM_PROVIDER` environment variable.

Supported providers:

- `openai` (Requires `OPENAI_API_KEY`)
- `anthropic` (Requires `ANTHROPIC_API_KEY`)
- `gemini` (Requires `GOOGLE_API_KEY`)
- `gh` (Requires `GH_API_KEY` or `GITHUB_TOKEN`)

#### 2. Providing Credentials

You have two options to provide credentials:

**Option A: Environment Variables (Recommended for local dev)**
Export the key in your shell configuration or current session:

```bash
export OPENAI_API_KEY="sk-..."
```

**Option B: Secret Store (Recommended for security)**
Use the agent's built-in secure storage:

```bash
agent onboard
# follow prompts to enter API keys
```

Or manually:

```bash
agent secret set openai api_key
```

### Mocking for Tests

If you are running tests, ensure you mock the credential headers or set dummy environment variables in your test runner configuration (e.g., `conftest.py` or `pytest.ini`). Do not commit real keys to the repository.

## 🔄 Environment Sync

The `agent sync` command manages bidirectional synchronization between your local environment and configured backends (e.g. Supabase, Notion).

```bash
agent sync pull [--backend=notion] [--force]
agent sync push [--backend=notion] [--force]
```

It supports:

- **Multiple Backends**: Target specific backends or sync all.
- **Interactive Conflict Resolution**: Prompts when content differs between local and remote.
- **Self-Healing**: Detects missing environments (e.g., Notion 404s) and offers to bootstrap them via `agent sync init`.
- **Janitor**: `agent sync janitor` ensures relational integrity (linking Stories to Plans/ADRs).

## 🧠 AI Assisted Workflows

The agent supports AI-driven content generation and review. Use the `--ai` flag to enable these features.

### Create Content

Generate drafts with AI context:

```bash
agent new-story <STORY_ID> --ai --prompt "Implement a new caching layer for the user profile service"
agent new-plan <PLAN_ID> --ai --prompt "Migration plan for upgrading to Postgres 16"
```

### Governance Review

Run AI-powered preflight checks:

```bash
agent preflight --story <STORY_ID> --ai
```
