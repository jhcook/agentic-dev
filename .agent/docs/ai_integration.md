# AI Integration Guide

Everything you need to know about AI providers, model selection, and token management.

## Supported Providers

### 1. Google Gemini (Recommended)

**Advantages:**

- Largest context window (1M tokens)
- Excellent code understanding
- Competitive pricing
- Fast response times

**Setup:**

```bash
export GEMINI_API_KEY="AIza..."
# Or
export GOOGLE_GEMINI_API_KEY="AIza..."
```

**Get API Key:**

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create new API key
3. Copy and export

**Models used:**

- `gemini-1.5-pro` - Complex tasks (runbooks, governance)
- `gemini-1.5-flash` - Simple tasks (commit messages)

### 2. OpenAI

**Advantages:**

- High quality responses
- Well-documented
- Wide adoption

**Setup:**

```bash
export OPENAI_API_KEY="sk-..."
```

**Get API Key:**

1. Visit [OpenAI Platform](https://platform.openai.com/api-keys)
2. Create new API key
3. Add payment method (usage-based billing)

**Models used:**

- `gpt-4o` - Primary model
- `gpt-4o-mini` - Cheaper alternative

### 3. GitHub CLI (Fallback)

**Advantages:**

- Free (no API key needed)
- Easy setup

**Limitations:**

- Small context window (8k tokens)
- Slower responses
- Limited availability

**Setup:**

```bash
# Install GitHub CLI
brew install gh

# Authenticate
gh auth login
```

**Model:**

- `gh models run gpt-4o`

### 4. Anthropic Claude 4.5 (NEW)

**Advantages:**

- Large context window (200K tokens)
- Excellent reasoning and coding
- **Streaming support** prevents timeouts
- Three model tiers for flexibility

**Limitations:**

- Requires paid API key (no free tier)
- Moderate pricing

**Setup:**

```bash
export ANTHROPIC_API_KEY="sk-ant-api03-..."
```

**Get API Key:**

1. Visit [Anthropic Console](https://console.anthropic.com/settings/keys)
2. Create new API key
3. Add payment method (usage-based billing)
4. Copy and export

**Models available:**

- `claude-sonnet-4-5-20250929` - Advanced tier (balanced performance/cost)
- `claude-haiku-4-5-20250929` - Standard tier (fast, economical)
- `claude-opus-4-5-20250929` - Premium tier (highest quality)

**Streaming:**
Claude uses streaming API to handle large contexts without timeouts:

```python
# Automatic streaming in agent
with client.messages.stream(
    model="claude-sonnet-4-5-20250929",
    max_tokens=4096,
    system=system_prompt,
    messages=[{"role": "user", "content": user_prompt}]
) as stream:
    for text in stream.text_stream:
        full_text += text
```

**Provider selection:**

```bash
# Use Anthropic explicitly
agent --provider anthropic new-runbook WEB-001

# Or set as default
export AGENT_DEFAULT_PROVIDER="anthropic"
```

## Model Selection

### Automatic Routing

The Agent uses a Smart Router that selects models based on:

1. **Available providers** - Which API keys are set
2. **Context size** - How much text needs to be analyzed
3. **Task complexity** - Defined in `.agent/etc/router.yaml`
4. **Cost optimization** - Prefers cheaper models when suitable

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
# Use Gemini for everything
agent --provider gemini new-runbook WEB-001
agent --provider gemini preflight --story WEB-001 --ai

# Use OpenAI
agent --provider openai new-runbook WEB-001

# Use GitHub CLI
agent --provider gh new-runbook WEB-001
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

  gemini-1.5-flash:
     provider: gemini
     tier: standard
     context_window: 1048576
     cost_per_1k_input: 0.00001875

  gpt-4o:
    provider: openai
    tier: advanced
    context_window: 128000
    cost_per_1k_input: 0.005

settings:
  # Default provider priority
  provider_priority:
    - gemini
    - openai
    - gh
  
  # Which tier to use by default if not specified
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

```python
# Large diff: 150k tokens
# Context window: 128k tokens

# Agent splits into chunks:
Chunk 1: 60k tokens (files A, B, C)
Chunk 2: 60k tokens (files D, E, F)
Chunk 3: 30k tokens (files G, H)

# Each chunk reviewed separately
# Results aggregated
```

**Configure chunk size:**

```bash
export AGENT_CHUNK_SIZE=6000  # characters per chunk
```

### Cost Optimization

**Pricing (approximate):**

| Model | Cost per 1M tokens | 100k token task |
|-------|-------------------|--------------------|
| gemini-1.5-pro | $1.25 | $0.125 |
| gpt-4o | $2.50 | $0.250 |
| claude-sonnet-4-5 | $3.00/$15.00 | $0.30/$1.50 |
| gemini-1.5-flash | $0.075 | $0.0075 |
| gpt-4o-mini | $0.15 | $0.015 |
| claude-haiku-4-5 | $1.00/$5.00 | $0.10/$0.50 |
| claude-opus-4-5 | $15.00/$75.00 | $1.50/$7.50 |
| github (gh cli) | Free | $0 |

*Note: Claude pricing shows input/output costs*

**Cost-saving tips:**

1. **Use tier2 for simple tasks:**

   ```yaml
   default_tier: tier2  # In router.yaml
   ```

2. **Reduce chunk size:**

   ```bash
   export AGENT_CHUNK_SIZE=4000  # Smaller chunks
   ```

3. **Limit governance roles (smaller teams):**

   ```yaml
   # Only essential roles
   team:
     - role: security
     - role: qa
   ```

4. **Use GitHub CLI when possible:**

   ```bash
   agent --provider gh commit --ai
   ```

## AI Commands

### 1. Runbook Generation

```bash
agent new-runbook WEB-001
```

**Process:**

1. Load story: ~2k tokens
2. Load governance rules: ~10k tokens  
3. Generate runbook: ~20k tokens output
4. Total: ~32k tokens (~$0.04 with Gemini)

**Prompt structure:**

```
System: You are an Implementation Planning Agent...

User:
STORY CONTENT:
[story markdown]

GOVERNANCE RULES:
[rules from .agent/rules/]

ROLE INSTRUCTIONS:
[instructions from .agent/instructions/]

Generate a detailed runbook in markdown format.
```

### 2. Governance Panel Review

```bash
agent preflight --story WEB-001 --ai
```

**Process:**

1. Load story: ~2k tokens
2. Get diff: ~50k tokens (varies)
3. Load rules: ~10k tokens
4. For each of 9 roles:
   - Send context: ~62k tokens
   - Get feedback: ~5k tokens
5. Total: ~600k tokens + overhead (~$0.75)

**Panel review is expensive but thorough!**

### 3. Story Matching

```bash
agent match-story --files "src/auth/login.py src/auth/middleware.py"
```

**Process:**

1. Load file list: ~0.5k tokens
2. Load all stories: ~20k tokens
3. Match algorithm: ~5k tokens output
4. Total: ~25k tokens (~$0.03)

### 4. Commit Message Generation

```bash
agent commit --story WEB-001 --ai
```

**Process:**

1. Get staged diff: ~10k tokens
2. Load story: ~2k tokens
3. Generate message: ~0.2k tokens output
4. Total: ~12k tokens (~$0.015)

**Very cheap, use freely!**

## Rate Limiting

### Provider Limits

**Google Gemini:**

- Free tier: 15 RPM, 1 million TPM
- Paid tier: 360 RPM, 4 million TPM

**OpenAI:**

- Tier 1: 500 RPM, 30k TPM
- Tier 5: 10k RPM, 200k TPM

### Handling Rate Limits

The Agent automatically retries with exponential backoff:

```python
# Built-in retry logic
max_retries = 3
for attempt in range(max_retries):
    try:
        response = ai_service.complete(system, user)
        break
    except RateLimitError:
        wait = 2 ** attempt  # 2s, 4s, 8s
        time.sleep(wait)
```

**Manual rate limit handling:**

```bash
# Slow down between calls
agent new-runbook WEB-001
sleep 5
agent new-runbook WEB-002
sleep 5
agent new-runbook WEB-003
```

## Advanced Features

### Context Truncation

For GitHub CLI's small context window, the Agent truncates rules:

```python
def truncate_governance_context(rules: str, max_tokens: int = 3000) -> str:
    """Truncate rules to fit in context window."""
    if count_tokens(rules) > max_tokens:
        # Keep only critical sections
        return extract_summary(rules, max_tokens)
    return rules
```

This ensures **something works** even with limited context.

### Multi-Turn Conversations

For complex tasks, the Agent may make multiple AI calls:

```bash
agent preflight --story WEB-001 --ai
```

1. **Turn 1**: "Review this diff" → Get initial feedback
2. **Turn 2**: "Analyze test coverage" → Detailed test analysis
3. **Turn 3**: "Check compliance" → GDPR/SOC2 validation

Each turn adds cost, but improves quality.

### Custom Prompts

For advanced users, you can customize prompts in the source:

**File:** `.agent/src/agent/commands/runbook.py`

```python
system_prompt = """You are an Implementation Planning Agent.

Your goal is to create a detailed, step-by-step runbook.

# Custom Instructions:
- Include rollback steps for every major change
- Estimate time for each step
- Flag high-risk operations

# Output Format:
... (rest of prompt)
"""
```

Restart required:

```bash
# Restart any running agent processes
# Changes take effect immediately
```

## Troubleshooting AI Issues

### "AI returned empty response"

**Causes:**

- API key invalid
- Rate limit exceeded
- Context too large
- Network issue

**Solutions:**

```bash
# Check API key
echo $GEMINI_API_KEY

# Try different provider
agent --provider openai new-runbook WEB-001

# Reduce context
export AGENT_CHUNK_SIZE=3000
```

### "Context window exceeded"

**Error:** `context_length_exceeded`

**Solution:**

```bash
# Enable chunking (should be automatic)
# Or use larger context model
agent --provider gemini new-runbook WEB-001
```

### "Rate limit exceeded"

**Error:** `rate_limit_exceeded`

**Solution:**

```bash
# Wait and retry
sleep 60
agent new-runbook WEB-001

# Or use different provider
agent --provider openai new-runbook WEB-001
```

### Poor quality responses

**Symptoms:**

- Runbook missing steps
- Garbage output
- Incomplete analysis

**Solutions:**

1. **Use higher-tier model:**

   ```bash
   agent --provider gemini new-runbook WEB-001
   ```

2. **Improve story quality:**
   - More detailed problem statement
   - Clearer acceptance criteria
   - Better context

3. **Update governance rules:**
   - Add examples in `.agent/rules/`
   - More specific instructions

4. **Regenerate:**

   ```bash
   # Delete and try again
   rm .agent/cache/runbooks/WEB/WEB-001-runbook.md
   agent new-runbook WEB-001
   ```

## Best Practices

1. **Set up Gemini first** - Best balance of cost/quality
2. **Keep OpenAI as backup** - Higher quality for complex tasks
3. **Monitor token usage** - Track costs over time
4. **Use cheaper models for simple tasks** - Configure router.yaml
5. **Cache expensive operations** - Don't regenerate runbooks unnecessarily
6. **Review AI output** - Never blindly trust AI-generated code

---

**Next**: [Troubleshooting](troubleshooting.md) →
