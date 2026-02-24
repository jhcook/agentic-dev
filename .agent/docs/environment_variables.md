# Environment Variables Reference

The Agentic Development Tool (`agent`) supports various environment variables for configuration. While many of these can be set in `.agent/etc/agent.yaml` or managed via the secure keyring (`agent secret`), environment variables offer a convenient way to override settings.

## Setting Variables via Config

Variables read from the environment can often be persisted permanently via the `agent config` command under the `env` config namespace. This updates `.agent/etc/agent.yaml` under the hood.

```bash
# Set a persistent timeout value across all sessions
agent config set env.AGENT_AI_TIMEOUT_MS "60000"

# Allow more concurrent ADK API calls
agent config set env.AGENT_MAX_CONCURRENT_API_CALLS "10"

# View your current managed environment variables
agent config list
```

> [!WARNING]
> While `agent config` is useful for general settings (like timeouts and concurrency limits), it stores values in plain text in `.agent/etc/agent.yaml`. **Do not use `agent config` for sensitive information like API keys or tokens.** Instead, use the secure keyring via `agent secret set <provider> <key>`. See the [Secret Management Guide](secret_management.md) for more details.

## AI Provider Configuration

Authentication and configuration for the supported AI models.

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | API key for Google Gemini provider. |
| `GOOGLE_API_KEY` | Fallback API key for Google Gemini provider. |
| `GOOGLE_CLOUD_PROJECT` | GCP Project ID used for Vertex AI provider. |
| `GOOGLE_CLOUD_LOCATION` | GCP Region used for Vertex AI provider (default: `us-central1`). |
| `OPENAI_API_KEY` | API key for OpenAI provider. |
| `OPENAI_MODEL` | Default OpenAI model to use if not specified in config (default: `gpt-4o`). |
| `ANTHROPIC_API_KEY` | API key for Anthropic provider. |
| `GITHUB_TOKEN` | Authentication token for GitHub Copilot / Models integration. |
| `HF_TOKEN` | Authentication token for HuggingFace provider. |
| `LLM_PROVIDER` | Override the default AI provider (e.g., `gemini`, `vertex`, `openai`). |
| `LLM_API_KEY` | Generic fallback API key for the selected `LLM_PROVIDER`. |

## Agent System Settings

Core operational parameters for the Agent CLI.

| Variable | Description |
|----------|-------------|
| `AGENT_ROOT` | Overrides the repository root path detection. |
| `AGENT_MASTER_KEY` | Master key for AES-256 encrypted secret management in keyring. |
| `AGENT_AI_TIMEOUT_MS` | Maximum time (in milliseconds) to wait for an AI provider response. |
| `AGENT_MCP_TIMEOUT` | Maximum time (in seconds) to wait for Model Context Protocol (MCP) server operations. |
| `AGENT_MAX_CONCURRENT_API_CALLS` | Maximum concurrent API calls allowed during parallel operations like the ADK governance panel. |
| `AGENT_VOICE_MODE` | Set to `"1"` to enable specific optimizations or context adjustments for the voice agent mode. |
| `LOG_LEVEL` | Application logging verbosity (e.g., `INFO`, `DEBUG`). |
| `CI` | If set to `true`, `1`, or `yes`, certain interactive prompts or outputs are suppressed for CI environments. |

## Network Configurations

Proxy settings for enterprise environments.

| Variable | Description |
|----------|-------------|
| `NO_PROXY` | Comma-separated list of domains to bypass proxies. The agent automatically appends Google/AI endpoints to this list if defined. |
| `no_proxy` | Lowercase equivalent of `NO_PROXY`. |

## Notion Integration

Variables for the bidirectional Notion sync pipeline.

| Variable | Description |
|----------|-------------|
| `NOTION_TOKEN` | Internal integration token for the Notion API. |
| `NOTION_DB_ID` | The Notion Database ID used for synchronization. |
| `NOTION_PARENT_PAGE_ID` | The parent page ID for initial Notion setup/onboarding. |
| `NOTION_TIMEOUT` | Request timeout in seconds for Notion API calls (default: `30`). |
| `AGENT_SYNC_PAGE_SIZE` | Pagination size for fetching Notion blocks/pages (default: `100`). |

## Voice & Audio

Backend transcription and speech synthesis parameters.

| Variable | Description |
|----------|-------------|
| `TTS_PROVIDER` | Defines the Text-to-Speech provider to use (e.g., Google, Deepgram). |
| `STT_PROVIDER` | Defines the Speech-to-Text provider to use (e.g., Google, Deepgram). |
| `SILERO_MODEL_URL` | Override URL for the Silero VAD (Voice Activity Detection) model download. |
| `EDITOR` | Custom terminal editor to use for interactive voice session fixes (fallback: `vim`). |

## Copyright

Copyright 2026 Justin Cook
