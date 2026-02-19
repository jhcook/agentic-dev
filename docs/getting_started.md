# Getting Started

## Provider Selection

The Agent CLI supports multiple AI providers. Set your provider in `.agent/etc/agent.yaml`:

```yaml
agent:
  provider: gemini   # or: vertex, openai, anthropic, gh
```

### Provider Comparison

| Provider | Auth Method | Rate Limits | Best For |
|----------|-------------|-------------|----------|
| **Gemini** (default) | `GEMINI_API_KEY` | Free-tier limits | Quick prototyping, personal use |
| **Vertex AI** | ADC (`gcloud auth`) | Pay-as-you-go, high | Production workloads, multi-agent panels |
| **OpenAI** | `OPENAI_API_KEY` | Plan-based | GPT-4o access |
| **Anthropic** | `ANTHROPIC_API_KEY` | Plan-based | Claude access |
| **GitHub CLI** | `gh` CLI auth | Copilot limits | GitHub-integrated workflows |

## Vertex AI Setup

Vertex AI uses [Application Default Credentials (ADC)](https://cloud.google.com/docs/authentication/application-default-credentials) — no API key needed.

### Prerequisites

1. A GCP project with the [Vertex AI API enabled](https://console.cloud.google.com/apis/library/aiplatform.googleapis.com)
2. `gcloud` CLI installed and authenticated

### Steps

```bash
# 1. Authenticate with GCP
gcloud auth application-default login

# 2. Set your project
export GOOGLE_CLOUD_PROJECT="your-project-id"

# 3. (Optional) Set region — defaults to us-central1
export GOOGLE_CLOUD_LOCATION="us-central1"

# 4. Update agent.yaml
# provider: vertex
```

### Verification

```bash
agent query "Hello from Vertex AI"
```

You should see the response without any API key errors.

## Gemini (AI Studio) Setup

```bash
# Get a key from https://aistudio.google.com/apikey
export GEMINI_API_KEY="AIza..."
```

## Fallback Behavior

When a provider hits rate limits or errors, the CLI automatically falls back through the chain:

```
gh → gemini → vertex → openai → anthropic
```

Set `provider` in `agent.yaml` to control which is tried first. The fallback chain is deterministic and skips providers without credentials.
