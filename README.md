# Agent CLI - AI-Powered Governance Framework

> **Governance by Code**: Enforce architectural standards, compliance (SOC2/GDPR), and quality assurance through an intelligent CLI that acts as your development team's governance layer.

## What is Agent?

**Agent** is an AI-powered CLI tool that automates governance, compliance, and quality checks for software development teams. It replaces manual code reviews with a systematic, AI-assisted workflow that ensures every change meets your team's standards before it reaches production.

Think of it as your **virtual governance team** that:
- ✅ Reviews code for architecture violations
- ✅ Enforces compliance (GDPR, SOC2)
- ✅ Validates test coverage and documentation
- ✅ Generates implementation plans and runbooks
- ✅ Automates preflight checks before commits

## Key Features

### 🤖 AI-Powered Workflows
- **Smart Planning**: Generate implementation plans from stories
- **Runbook Generation**: Create step-by-step execution guides
- **Code Implementation**: AI-assisted code generation
- **Story Matching**: Automatically link commits to stories

### 🛡️ Governance Enforcement
- **9-Role Governance Panel**: Architect, QA, Security, Product, Observability, Docs, Compliance, Mobile, Web, Backend
- **State Management**: Enforced transitions (Plan → Story → Runbook → Implementation)
- **Compliance Checks**: SOC2, GDPR, PII detection, secrets scanning
- **Architectural Reviews**: ADR validation, boundary enforcement

### 🚀 Developer Experience
- **Interactive CLI**: Guided workflows with smart defaults
- **Multi-Provider AI**: Google Gemini, OpenAI, GitHub CLI
- **Smart Routing**: Automatic model selection based on task complexity
- **Token Optimization**: Efficient context management

### 🔄 Distributed Synchronization
- **SQLite Local Cache**: Efficient offline access to stories and plans
- **Supabase Cloud Sync**: Real-time collaboration with remote teams
- **Bi-Directional Sync**: Seamlessly push and pull changes
- **Auto-Linking**: Automatically links Plans, Stories, and ADRs
- **Conflict Resolution**: Composite key architecture to prevent collisions

## Quick Start


### Installation

```bash
# Clone the repository
git clone <your-repo>
cd <your-repo>

# Install dependencies
pip install -r .agent/requirements.txt

# Add to PATH (or use full path ./.agent/bin/agent)
export PATH="$PATH:$(pwd)/.agent/bin"

# Initialize Sync Database
python .agent/src/agent/db/init.py

# Configure Supabase Key (Secure)
echo "your-service-role-key" > .agent/secrets/supabase_key
```

### Basic Workflow

```bash
# 1. Create a new story
agent new-story

# 2. Generate a runbook
agent new-runbook INFRA-001
# (Runbook is auto-synced to local cache)

# 2a. Check Sync Status
python .agent/src/agent/sync/sync.py status

# 3. Run preflight checks
agent preflight --story INFRA-001 --ai

# 4. Commit with governance
agent commit --story INFRA-001

# 5. Create a pull request
agent pr --story INFRA-001
```

## Documentation

📚 **Comprehensive guides available in `/docs`:**

- **[Getting Started](docs/getting_started.md)** - Installation, configuration, first steps
- **[Commands Reference](docs/commands.md)** - Complete CLI command documentation
- **[Governance System](docs/governance.md)** - Understanding roles, rules, and compliance
- **[Workflows](docs/workflows.md)** - Story-driven development process
- **[Configuration](docs/configuration.md)** - Customizing the agent for your team
- **[AI Integration](docs/ai_integration.md)** - Provider setup, model selection, token management
- **[Rules & Instructions](docs/rules_and_instructions.md)** - Creating custom governance rules
- **[Troubleshooting](docs/troubleshooting.md)** - Common issues and solutions

## Core Concepts

### Story-Driven Development

Agent enforces a structured development workflow:

```
Plan (APPROVED) → Stories (COMMITTED) → Runbooks (ACCEPTED) → Implementation
```

1. **Plans** - High-level epics that contain multiple stories
2. **Stories** - Individual tasks with acceptance criteria
3. **Runbooks** - Step-by-step implementation guides
4. **Implementation** - AI-assisted code generation

### Governance Panel

The AI Governance Panel consists of 9 specialized roles that review your code:

| Role | Focus Area |
|------|-----------|
| **Architect** | System design, ADR compliance, boundaries |
| **QA** | Test coverage, testing strategies |
| **Security** | Secrets, vulnerabilities, security posture |
| **Product** | Acceptance criteria, user value |
| **Observability** | Metrics, tracing, logging |
| **Docs** | Documentation synchronization |
| **Compliance** | SOC2, GDPR enforcement |
| **Mobile** | React Native, Expo patterns |
| **Web** | Next.js, SEO, accessibility |
| **Backend** | FastAPI, Python, API contracts |

### Directory Structure

```
.agent/
├── bin/agent              # CLI executable
├── src/                   # Python implementation
│   ├── agent/
│   │   ├── commands/      # CLI commands
│   │   └── core/          # Core logic (AI, routing, config)
├── cache/                 # Generated artifacts
│   ├── stories/           # Story files (INFRA/, WEB/, MOBILE/, BACKEND/)
│   ├── plans/             # Plan files
│   └── runbooks/          # Runbook files
├── templates/             # Templates for stories, plans, runbooks, ADRs
├── rules/                 # Global governance rules
├── instructions/          # Role-specific instructions
├── compliance/            # SOC2, GDPR documentation
├── workflows/             # Workflow definitions
└── etc/                   # Configuration (agents.yaml, router.yaml)
```

## AI Providers

Agent supports multiple AI providers with automatic fallback:

1. **Google Gemini** (Recommended)
   - Set `GEMINI_API_KEY` or `GOOGLE_GEMINI_API_KEY`
   - Uses `gemini-1.5-pro` with large context windows

2. **OpenAI**
   - Set `OPENAI_API_KEY`
   - Uses `gpt-4o` for complex tasks

3. **GitHub CLI** (Fallback)
   - No API key required
   - Uses `gh models run` with limited context

## Example: Creating a Feature

```bash
# 1. Create a story for your feature
$ agent new-story
Select Story Category:
1. INFRA (Governance, CI/CD)
2. WEB (Frontend)
3. MOBILE (React Native)
4. BACKEND (FastAPI)
Choice: 2

Enter Story Title: Add dark mode toggle
✅ Created Story: .agent/cache/stories/WEB/WEB-001-add-dark-mode-toggle.md

# 2. Generate an implementation runbook
$ agent new-runbook WEB-001
🤖 AI is thinking...
✅ Runbook generated at: .agent/cache/runbooks/WEB/WEB-001-runbook.md

# 3. Run preflight with AI governance panel
$ agent preflight --story WEB-001 --ai
🔍 Running preflight checks for WEB-001...
✅ @Architect: No architectural violations
✅ @Security: No secrets or PII detected
✅ @QA: Test coverage adequate
⚠️  @Docs: Missing CHANGELOG entry
❌ PREFLIGHT FAILED

# 4. Fix issues and commit
$ agent commit --story WEB-001 --ai
🤖 Generating commit message...
✅ feat(web): add dark mode toggle component [WEB-001]

# 5. Create pull request
$ agent pr --story WEB-001
✅ Pull request created: https://github.com/...
```

## Contributing

See [docs/contributing.md](docs/contributing.md) for development setup and guidelines.

## License

[Your License Here]

## Support

- **Documentation**: `/docs` directory
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions

---

**Built with ❤️ for developers who care about quality**
