# Gemini Provider Configuration

Google Gemini is the **recommended** default provider for the agent framework, offering the largest context window and competitive pricing.

## Advantages

- Largest context window (1M tokens)
- Excellent code understanding
- Competitive pricing
- Fast response times

## Setup

```bash
export GEMINI_API_KEY="AIza..."
```

**Get API Key:**

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create new API key
3. Copy and export

## Models

| Model | Tier | Use Case |
|-------|------|----------|
| `gemini-2.5-pro` | Advanced | Complex tasks (runbooks, governance) |
| `gemini-1.5-flash` | Standard | Simple tasks (commit messages) |

## Rate Limits

| Tier | RPM | TPM |
|------|-----|-----|
| Free | 15 | 1,000,000 |
| Paid | 360 | 4,000,000 |

## Pricing

| Model | Cost per 1M tokens |
|-------|-------------------|
| `gemini-1.5-pro` | $1.25 |
| `gemini-1.5-flash` | $0.075 |

## Provider Selection

```bash
# Use Gemini explicitly
agent --provider gemini new-runbook WEB-001

# Or set as default
export AGENT_DEFAULT_PROVIDER="gemini"
```

## Copyright

Copyright 2026 Justin Cook
