# Agent

## Troubleshooting: Missing Credentials

The agent requires credentials for certain commands that interact with AI providers (e.g., OpenAI, Anthropic, Gemini). If you encounter an error message like:

`[❌ Missing Credentials] The following required credentials are not found: - OPENAI_API_KEY`

It means the agent cannot authenticate with the configured AI provider.

### Resolution

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
