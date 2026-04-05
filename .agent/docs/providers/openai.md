# OpenAI Provider Configuration

OpenAI provides high-quality responses with wide adoption and a well-documented API.

## Advantages

- High quality responses
- Well-documented API
- Wide adoption and ecosystem

## Setup

```bash
export OPENAI_API_KEY="sk-..."
```

**Get API Key:**

1. Visit [OpenAI Platform](https://platform.openai.com/api-keys)
2. Create new API key
3. Add payment method (usage-based billing)

## Models

| Model | Tier | Use Case |
|-------|------|----------|
| `gpt-4o` | Advanced | Primary model for complex tasks |
| `gpt-4o-mini` | Standard | Cheaper alternative for simple tasks |

## Rate Limits

| Tier | RPM | TPM |
|------|-----|-----|
| Tier 1 | 500 | 30,000 |
| Tier 5 | 10,000 | 200,000 |

## Pricing

| Model | Cost per 1M tokens |
|-------|-------------------|
| `gpt-4o` | $2.50 |
| `gpt-4o-mini` | $0.15 |

## Provider Selection

```bash
# Use OpenAI explicitly
agent --provider openai new-runbook WEB-001

# Or set as default
export AGENT_DEFAULT_PROVIDER="openai"
```

## Copyright

Copyright 2026 Justin Cook
