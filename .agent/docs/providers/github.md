# GitHub CLI Provider Configuration

The GitHub CLI provider is a **free fallback** that requires no API key — it piggybacks on your existing `gh` authentication.

## Advantages

- Free (no API key needed)
- Easy setup — just `gh auth login`
- Good fallback when other providers are unavailable

## Limitations

- Small context window (8k tokens)
- Slower responses
- Limited model availability

## Setup

```bash
# Install GitHub CLI
brew install gh

# Authenticate
gh auth login
```

No API key or environment variable is needed — the provider uses `gh models run` directly.

## Models

| Model | Notes |
|-------|-------|
| `openai/gpt-4o` | Accessed via GitHub Models |

## Pricing

Free (covered by GitHub).

## Context Handling

Because of the small context window, the agent automatically truncates governance rules when using this provider:

```python
def truncate_governance_context(rules: str, max_tokens: int = 3000) -> str:
    """Truncate rules to fit in context window."""
    if count_tokens(rules) > max_tokens:
        return extract_summary(rules, max_tokens)
    return rules
```

This ensures **something works** even with limited context.

## Provider Selection

```bash
# Use GitHub CLI explicitly
agent --provider gh new-runbook WEB-001
agent --provider gh commit
```

## Copyright

Copyright 2026 Justin Cook
