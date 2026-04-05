# Claude Provider Configuration

The Claude provider is a unified interface for accessing Anthropic's Claude models. It is designed to be compatible with existing [Claude Code](https://claude.ai/code) configurations while providing flexible routing through either the direct Anthropic API or AWS Bedrock.

## Configuration Discovery

The provider automatically looks for configuration in two places:
1. The system environment (OS environment variables).
2. The standard Claude Code settings file located at `~/.claude/settings.json`.

### Precedence Order

1. **Explicit environment variables** — always take priority. If `AWS_REGION` is set in your shell, it will not be overwritten by the value in `settings.json`.
2. **`~/.claude/settings.json` `env` block** — injected into `os.environ` only for keys that are not already present.
3. **Default SDK behaviour** — the Anthropic SDK's own credential chain (e.g. `~/.aws/credentials`).

### Settings File Format

The agent specifically parses the `env` block and the `awsAuthRefresh` command from the settings file:

```json
{
  "env": {
    "CLAUDE_CODE_USE_BEDROCK": "1",
    "AWS_REGION": "us-east-1",
    "AWS_PROFILE": "my-developer-profile",
    "ANTHROPIC_MODEL": "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
  },
  "awsAuthRefresh": "aws sso login --profile my-developer-profile"
}
```

## AWS Bedrock Integration

When `CLAUDE_CODE_USE_BEDROCK=1` is detected (from settings or env), the provider builds an `AnthropicBedrock` client.

- **Region**: Read from `AWS_REGION`.
- **Profile**: Read from `AWS_PROFILE` (optional).
- **SSO Refresh**: If `awsAuthRefresh` is present in `settings.json`, it is executed before client construction to refresh SSO credentials automatically. The command runs with a 60-second timeout; failures are logged but do not block startup.

## Direct Anthropic API

When Bedrock is NOT enabled, the provider falls back to the standard `Anthropic` client using `ANTHROPIC_API_KEY` from the environment. If no API key is found, an `AIConfigurationError` is raised with guidance for running `agent onboard`.

## Smart Routing & Models

The `claude` provider is registered with the following model mappings:

| Model ID              | Description             |
|-----------------------|-------------------------|
| `claude-3-5-sonnet`   | Claude 3.5 Sonnet       |
| `claude-3-haiku`      | Claude 3 Haiku (fast)   |
| `claude-3-opus`       | Claude 3 Opus (premium) |

The `claude-*` prefix resolves to `ClaudeProvider` automatically via the prefix fallback map.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `AIConfigurationError: ANTHROPIC_API_KEY is not set` | No API key and Bedrock not enabled | Set `ANTHROPIC_API_KEY` or configure Bedrock in `~/.claude/settings.json` |
| `auth refresh command timed out` | SSO session expired and refresh command hung | Run `aws sso login --profile <profile>` manually |
| `auth refresh command not found` | `awsAuthRefresh` points to missing binary | Verify the command in `~/.claude/settings.json` is correct |
| Provider not available in `agent provider` | Not registered | Ensure `agent.yaml` has a `claude` entry under `models` |

## Copyright

Copyright 2026 Justin Cook
