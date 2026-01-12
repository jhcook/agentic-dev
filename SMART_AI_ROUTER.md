# Smart AI Router

**Status:** Implementation In Progress
**Language:** Python
**Config:** `.agent/router.yaml`

## Overview

The Smart AI Router is a Python-based module within the `agent` CLI that intelligently routes AI requests to the most appropriate model based on:
1.  **Complexity/Tier**: Matching the task difficulty to the model capability.
2.  **Context Window**: Ensuring the input fits within the model's limits.
3.  **Cost Efficiency**: Selecting the cheapest model that satisfies the above constraints.

## Configuration

The router is configured via `.agent/router.yaml`.

### Schema

```yaml
version: 1.0

models:
  <model_key>:
    provider: "openai" | "gemini" | "gh"
    deployment_id: string
    tier: "light" | "standard" | "advanced"
    context_window: integer
    cost_per_1k_input: float
    cost_per_1k_output: float
    supports_vision: boolean

settings:
  default_tier: "standard"
  provider_priority: list[string]
```

### Default Configuration

```yaml
version: 1.0

models:
  # --- OpenAI Models ---
  gpt-4o:
    provider: "openai"
    deployment_id: "gpt-4o"
    tier: "advanced"
    context_window: 128000
    cost_per_1k_input: 0.0025
    cost_per_1k_output: 0.0100
    supports_vision: true

  gpt-4o-mini:
    provider: "openai"
    deployment_id: "gpt-4o-mini"
    tier: "light"
    context_window: 128000
    cost_per_1k_input: 0.00015
    cost_per_1k_output: 0.00060

  # --- Gemini Models ---
  gemini-1.5-pro:
    provider: "gemini"
    deployment_id: "gemini-1.5-pro-latest"
    tier: "advanced"
    context_window: 2000000
    cost_per_1k_input: 0.00125
    cost_per_1k_output: 0.00500

  gemini-1.5-flash:
    provider: "gemini"
    deployment_id: "gemini-1.5-flash-latest"
    tier: "standard"
    context_window: 1000000
    cost_per_1k_input: 0.000075
    cost_per_1k_output: 0.000300

  # --- GitHub CLI ---
  gh-copilot:
    provider: "gh"
    deployment_id: "gpt-4o"
    tier: "standard"
    context_window: 8000
    cost_per_1k_input: 0.0000
    cost_per_1k_output: 0.0000

settings:
  default_tier: "standard"
  provider_priority: ["gemini", "openai", "gh"]
```

## Architecture

### Components

1.  **`TokenManager` (`agent.core.tokens`)**
    *   Responsible for counting tokens in prompt strings.
    *   Uses `tiktoken` for OpenAI models.
    *   Uses character-count heuristics (~4 chars/token) for others if native tokenizers are unavailable, keeping dependencies light.

2.  **`SmartRouter` (`agent.core.router`)**
    *   Loads configuration from `router.yaml`.
    *   **`route(prompt: str, tier: str = "standard") -> ModelConfig`**:
        1.  Calculates input token count.
        2.  Filters models by requested `tier` (or higher).
        3.  Filters models where `context_window` < `input_tokens`.
        4.  Sorts candidates by `cost_per_1k_input`.
        5.  Returns the best match.

3.  **`AIService` (`agent.core.ai`)**
    *   Integrated consumer of `SmartRouter`.
    *   Delegates model selection to the router before making API calls.

## Usage

The router operates transparently during AI commands.

```bash
# Explicitly requesting a tier (future flags)
agent preflight --ai --tier advanced

# The router treats default requests as "standard" tier
agent preflight --ai
```
