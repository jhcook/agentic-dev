# Agent Governance Framework

This directory contains the governance framework for the repo. It is designed to ensure strict adherence to architectural standards, compliance (SOC2/GDPR), and quality assurance through a "Governance by Code" approach.

## 📚 Complete Documentation

**For comprehensive documentation, see [`/docs`](../docs/README.md)**

The `/docs` directory contains detailed guides on:
- 📖 [Getting Started](../docs/getting_started.md) - Installation and initial setup
- 🛠️ [Commands Reference](../docs/commands.md) - All CLI commands
- 🛡️ [Governance System](../docs/governance.md) - How the AI panel works
- 🔄 [Workflows](../docs/workflows.md) - Story-driven development
- ⚙️ [Configuration](../docs/configuration.md) - Customizing for your team
- 🤖 [AI Integration](../docs/ai_integration.md) - Provider setup and optimization
- 📋 [Rules & Instructions](../docs/rules_and_instructions.md) - Custom governance
- 🔧 [Troubleshooting](../docs/troubleshooting.md) - Common issues

## Quick Start

```bash
# 1. Create a story
agent new-story

# 2. Generate runbook
agent new-runbook INFRA-001

# 3. Run preflight
agent preflight --story INFRA-001 --ai

# 4. Commit with governance
agent commit --story INFRA-001

# 5. Create PR
agent pr --story INFRA-001
```

## Core Concepts

### Story-Driven Development

```
Plan (APPROVED) → Stories (COMMITTED) → Runbooks (ACCEPTED) → Implementation
```

### Governance Panel

9 AI agents review your code:
- **@Architect** - System design, ADR compliance
- **@Security** - Secrets, vulnerabilities, PII
- **@QA** - Test coverage, strategies
- **@Product** - Acceptance criteria
- **@Observability** - Metrics, tracing
- **@Docs** - Documentation sync
- **@Compliance** - SOC2, GDPR
- **@Mobile** - React Native patterns
- **@Web** - Next.js, SEO
- **@Backend** - FastAPI, Python

### Directory Structure

```
.agent/
├── bin/agent              # CLI executable
├── src/                   # Python implementation
├── cache/                 # Generated artifacts
│   ├── stories/           # Story files
│   ├── plans/             # Plan files
│   └── runbooks/          # Runbook files
├── templates/             # Templates
├── rules/                 # Governance rules
├── instructions/          # Role instructions
├── compliance/            # SOC2, GDPR
├── workflows/             # Workflow definitions
├── etc/                   # Configuration
│   ├── agents.yaml
│   └── router.yaml
└── logs/                  # Preflight logs
```

## AI Providers

1. **Google Gemini** (Recommended) - Set `GEMINI_API_KEY`
2. **OpenAI** - Set `OPENAI_API_KEY`
3. **GitHub CLI** (Fallback) - Uses `gh models run`

## Development & Testing

```bash
# Install in editable mode with dependencies
pip install -e .agent/

# Run all tests
PYTHONPATH=.agent/src pytest .agent/tests/

# Run specific suite
PYTHONPATH=.agent/src pytest .agent/tests/commands/
```

---

**For detailed documentation**: [`/docs`](../docs/README.md)
