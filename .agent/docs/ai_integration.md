# AI Integration Guide

Everything you need to know about AI providers, model selection, and token management.

## Supported Providers

The agent supports multiple AI providers. Each provider has dedicated documentation
covering setup, models, pricing, and troubleshooting.

| Provider | Context Window | Pricing | Best For |
|----------|---------------|---------|----------|
| [**Google Gemini**](providers/gemini.md) ⭐ | 1M tokens | $0.075–$1.25/1M | Default — best cost/quality balance |
| [**OpenAI**](providers/openai.md) | 128K tokens | $0.15–$2.50/1M | High-quality fallback |
| [**Claude**](providers/claude.md) | 200K tokens | $1.00–$15.00/1M | Bedrock/SSO environments |
| [**GitHub CLI**](providers/github.md) | 8K tokens | Free | Quick tasks, no API key needed |

### Quick Setup

```bash
# Option 1: Gemini (recommended)
export GEMINI_API_KEY="AIza..."

# Option 2: OpenAI
export OPENAI_API_KEY="sk-..."

# Option 3: Claude (direct API)
export ANTHROPIC_API_KEY="sk-ant-api03-..."

# Option 4: Claude (AWS Bedrock — auto-detected from ~/.claude/settings.json)
# See providers/claude.md for details

# Option 5: GitHub CLI (free, no key needed)
brew install gh && gh auth login
```

## Model Selection

### Automatic Routing

The Agent uses a Smart Router that selects models based on:

1. **Available providers** — Which API keys are set
2. **Context size** — How much text needs to be analyzed
3. **Task complexity** — Defined in `.agent/etc/router.yaml`
4. **Cost optimization** — Prefers cheaper models when suitable

**Example routing decisions:**

| Task | Context Size | Model Selected |
|------|--------------|----------------|
| Generate runbook | Large (100k tokens) | gemini-2.5-pro |
| Match story | Small (2k tokens) | gemini-1.5-flash |
| Governance review | Large (50k tokens) | gpt-4o |
| Commit message | Tiny (500 tokens) | gpt-4o-mini |

### Manual Override

Force a specific provider:

```bash
agent --provider gemini new-runbook WEB-001
agent --provider openai preflight --story WEB-001
agent --provider claude new-runbook WEB-001
agent --provider gh commit
```

### Configuring Routing

Edit `.agent/etc/router.yaml`:

```yaml
models:
  gemini-2.5-pro:
    provider: gemini
    tier: advanced
    context_window: 1048576
    cost_per_1k_input: 0.000125

  gpt-4o:
    provider: openai
    tier: advanced
    context_window: 128000
    cost_per_1k_input: 0.005

settings:
  provider_priority: ["claude", "gemini", "openai", "ollama", "gh"]
  default_tier: standard
```

## Token Management

### Understanding Tokens

Tokens are chunks of text that AI models process:

- ~4 characters = 1 token
- ~750 words = 1000 tokens

**Context window** = Maximum tokens the model can process in one request.

### Token Counting

The Agent uses `tiktoken` to count tokens before sending to AI:

```python
from agent.core.tokens import token_manager

text = "Your code diff here..."
tokens = token_manager.count_tokens(text)
print(f"This will use {tokens} tokens")
```

### Smart Chunking

For large diffs that exceed context window, the Agent automatically chunks:

```
Chunk 1: 60k tokens (files A, B, C)
Chunk 2: 60k tokens (files D, E, F)
Chunk 3: 30k tokens (files G, H)
# Each chunk reviewed separately, results aggregated
```

**Configure chunk size:**

```bash
export AGENT_CHUNK_SIZE=6000  # characters per chunk
```

### Cost Optimization

**Approximate pricing (input tokens):**

| Model | Cost per 1M tokens | 100k token task |
|-------|-------------------|-----------------|
| gemini-1.5-pro | $1.25 | $0.125 |
| gpt-4o | $2.50 | $0.250 |
| claude-sonnet-4-5 | $3.00/$15.00 | $0.30/$1.50 |
| gemini-1.5-flash | $0.075 | $0.0075 |
| gpt-4o-mini | $0.15 | $0.015 |
| claude-haiku-4-5 | $1.00/$5.00 | $0.10/$0.50 |
| github (gh cli) | Free | $0 |

*Note: Claude pricing shows input/output costs. See [Claude provider docs](providers/claude.md) for details.*

**Cost-saving tips:**

1. Use `default_tier: standard` in `router.yaml` for simple tasks
2. Reduce chunk size: `export AGENT_CHUNK_SIZE=4000`
3. Limit governance roles for smaller teams
4. Use GitHub CLI for cheap operations like commit messages

## AI Commands

### Cost Estimates by Command

| Command | Typical Tokens | Estimated Cost (Gemini) |
|---------|---------------|------------------------|
| `agent new-runbook WEB-001` | ~32k | ~$0.04 |
| `agent preflight --story WEB-001` | ~600k (9 roles) | ~$0.75 |
| `agent match-story --files "..."` | ~25k | ~$0.03 |
| `agent commit --story WEB-001` | ~12k | ~$0.015 |

**Tips:**
- `preflight` is expensive but thorough — each of 9 governance roles reviews the full diff
- `commit` is very cheap — use freely
- Cache expensive operations — don't regenerate runbooks unnecessarily

## Troubleshooting AI Issues

| Symptom | Likely Cause | Solution |
|---------|-------------|----------|
| Empty response | Invalid API key, rate limit, context too large | Check key: `echo $GEMINI_API_KEY`, try another provider |
| `context_length_exceeded` | Diff too large for model | Use Gemini (1M window) or enable chunking |
| `rate_limit_exceeded` | Too many requests | Wait 60s, or switch provider |
| Poor quality output | Insufficient context, wrong tier | Use higher-tier model, improve story quality |

For provider-specific troubleshooting, see the individual provider docs:
- [Gemini troubleshooting](providers/gemini.md)
- [OpenAI troubleshooting](providers/openai.md)
- [Claude troubleshooting](providers/claude.md)
- [GitHub CLI troubleshooting](providers/github.md)

## Best Practices

1. **Set up Gemini first** — Best balance of cost/quality
2. **Keep OpenAI as backup** — Higher quality for complex tasks
3. **Use Claude for Bedrock environments** — Leverages existing SSO/settings
4. **Monitor token usage** — Track costs over time
5. **Use cheaper models for simple tasks** — Configure `router.yaml`
6. **Cache expensive operations** — Don't regenerate runbooks unnecessarily
7. **Review AI output** — Never blindly trust AI-generated code

---

**Next**: [Troubleshooting](troubleshooting.md) →
