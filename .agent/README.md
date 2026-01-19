# Agent Governance Framework

> **Governance by Code**: Enforce architectural standards, compliance (SOC2/GDPR), and quality assurance through an intelligent CLI that acts as your development team's governance layer.

This directory (`.agent/`) contains the complete governance framework.

## 📁 Directory Structure

```
.agent/
├── bin/agent              # CLI executable wrapper
├── src/                   # Core Python implementation
│   ├── agent/
│   │   ├── commands/      # CLI command modules
│   │   └── core/          # Core logic (AI, routing, config)
├── cache/                 # Local artifact cache (Synced via Supabase)
│   ├── stories/           # Feature definitions
│   ├── plans/             # High-level epics
│   └── runbooks/          # Implementation guides
├── templates/             # Markdown templates
├── rules/                 # Global governance rules (Markdown)
├── instructions/          # Role-specific AI instructions
├── compliance/            # SOC2/GDPR documentation
├── workflows/             # Workflow definitions
├── etc/                   # Configuration
│   ├── agents.yaml        # Agent role definitions
│   └── router.yaml        # AI Model routing config
└── logs/                  # Execution & Preflight logs
```

## 🧠 Core Concepts

### Story-Driven Development

Agent enforces a strict structured workflow to ensure quality:

```
Plan (APPROVED) → Stories (COMMITTED) → Runbooks (ACCEPTED) → Implementation
```

1. **Plans**: High-level epics or Requests for Comments (RFCs).
2. **Stories**: Individual units of work with rigorous Acceptance Criteria.
3. **Runbooks**: AI-generated step-by-step implementation guides.
4. **Implementation**: AI-assisted code generation based on the Runbook.

### The AI Governance Panel

Your code is reviewed by 9 specialized AI agents, each with a specific focus:

| Role | Focus Area |
|------|-----------|
| **@Architect** | System design, ADR compliance, boundaries |
| **@QA** | Test coverage, testing strategies |
| **@Security** | Secrets, vulnerabilities, security posture |
| **@Product** | Acceptance criteria, user value |
| **@Observability** | Metrics, tracing, logging |
| **@Docs** | Documentation synchronization |
| **@Compliance** | SOC2, GDPR enforcement |
| **@Mobile** | React Native, Expo patterns |
| **@Web** | Next.js, SEO, accessibility |
| **@Backend** | FastAPI, Python, API contracts |

## 🚀 Workflows

### 1. Creating a Feature

```bash
# 1. Create a story
agent new-story

# 2. Analyze Impact (Optional but recommended)
agent impact WEB-001 --ai --update-story

# 2. Generate runbook (AI analyzes story + rules)
agent new-runbook WEB-001

# 3. Run preflight (AI Governance Panel reviews)
agent preflight --story WEB-001 --ai

# 4. Commit (AI generates conventional commit)
agent commit --story WEB-001 --ai

# 5. Create PR
agent pr --story WEB-001
```

### 2. Synchronization

The agent supports syncing artifacts to a centralized Supabase backend for team collaboration.

```bash
# Push changes
agent sync push

# Pull changes
agent sync pull

# Check status
agent sync status
```

**Credentials**: Set `SUPABASE_ACCESS_TOKEN` in `.env` or `.agent/secrets/supabase_access_token`.

## ⚙️ Configuration

### AI Providers

1. **Google Gemini** (Recommended): Set `GEMINI_API_KEY` (Uses `gemini-1.5-pro`).
2. **OpenAI**: Set `OPENAI_API_KEY` (Uses `gpt-4o`).
3. **GitHub CLI** (Fallback): Uses `gh models run`.

### AI Model Discovery

Check which models are available to your agent:

```bash
agent list-models
agent list-models openai
```

### Secret Management

Store API keys encrypted instead of in environment variables:

```bash
# Initialize (first time)
agent secret init

# Import existing env vars
agent secret import openai
agent secret import supabase

# Or set manually
agent secret set gemini api_key

# List stored secrets
agent secret list
```

See [ADR-006](adrs/ADR-006-encrypted-secret-management.md) for details.

### Router Configuration


Customize model selection in `.agent/etc/router.yaml`:

```yaml
tiers:
  smart:
    providers: ["gemini", "openai"]
  fast:
    providers: ["gemini-flash", "gpt-4o-mini"]
```

**Manage Configuration via CLI:**

The `agent config` command allows you to view and modify configuration files without direct editing.

```bash
# List all configurations
agent config list

# Get a value (defaults to router.yaml)
agent config get models.gpt-4o.tier

# Get a value from a specific file (prefix routing)
agent config get agents.team.0.role

# Set a value (updates file safely with backup)
agent config set settings.default_tier advanced
```

## 🛠️ Development & Testing

If you are contributing to the Agent framework itself:

```bash
# Install in editable mode
pip install -e .agent/

# Install dev dependencies
brew install shellcheck
npm install -g eslint

# Run Tests
PYTHONPATH=.agent/src pytest .agent/tests/

# Linting
agent lint --all --fix
```

## 📚 Detailed Documentation

For specific guides, see the `docs/` folder:
- [Getting Started](docs/getting_started.md)
- [Commands Reference](docs/commands.md)
- [Governance System](docs/governance.md)
- [Rules & Instructions](docs/rules_and_instructions.md)
