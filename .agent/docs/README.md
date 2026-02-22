# Documentation Index

Complete documentation for the Agent CLI governance framework.

## Quick Links

- **[⚡ Getting Started](getting_started.md)** - Installation and first steps
- **[📖 Commands Reference](commands.md)** - Complete CLI command documentation
- **[🛡️ Governance System](governance.md)** - Understanding the AI review panel
- **[🔄 Workflows](workflows.md)** - Story-driven development process
- **[⚙️ Configuration](configuration.md)** - Customizing the agent
- **[🤖 AI Integration](ai_integration.md)** - Provider setup and token management
- **[🎤 Backend Voice](backend_voice.md)** - Voice provider architecture and WebSocket integration
- **[📋 Rules & Instructions](rules_and_instructions.md)** - Creating custom governance
- **[🔧 Troubleshooting](troubleshooting.md)** - Common issues and solutions

## Documentation by Topic

### For New Users

Start here if you're new to the Agent CLI:

1. **[Getting Started](getting_started.md)**
   - Installation instructions
   - API key setup
   - Your first story
   - Running preflight checks

2. **[Workflows](workflows.md)**
   - Story-driven development
   - Creating stories and runbooks
   - Commit and PR workflows
   - Best practices

3. **[Commands Reference](commands.md)**
   - All available commands
   - Command options and arguments
   - Usage examples

### For Developers

Deep dive into using the Agent CLI day-to-day:

1. **[Commands Reference](commands.md)**
   - `agent new-story` - Create stories
   - `agent new-runbook` - Generate implementation plans
   - `agent preflight` - Run governance checks
   - `agent commit` - Governed commits
   - `agent pr` - Create pull requests

2. **[Workflows](workflows.md)**
   - Feature development workflow
   - Bug fix workflow
   - Hotfix workflow
   - Refactoring workflow

3. **[AI Integration](ai_integration.md)**
   - Which AI provider to use
   - Token usage and costs
   - Model selection strategy

### For Team Leads

Setting up and customizing Agent for your team:

1. **[Governance System](governance.md)**
   - How the AI panel works
   - 9 governance roles explained
   - State enforcement rules
   - Review criteria by role

2. **[Configuration](configuration.md)**
   - Customizing agents.yaml
   - AI model routing (router.yaml)
   - Environment variables
   - CI/CD integration

3. **[Rules & Instructions](rules_and_instructions.md)**
   - Creating custom governance rules
   - Role-specific instructions
   - Compliance checklist (SOC2, GDPR)
   - Rule severity levels

### For Administrators

Technical setup and maintenance:

1. **[Configuration](configuration.md)**
   - Directory structure
   - Configuration files
   - Templates customization
   - Environment setup

2. **[AI Integration](ai_integration.md)**
   - Provider comparison
   - API key management
   - Rate limiting
   - Cost optimization

3. **[Troubleshooting](troubleshooting.md)**
   - Common errors and solutions
   - Debugging tools
   - Performance optimization
   - Getting help

## By Use Case

### "I want to create a new feature"

1. [Workflows: Feature Development](workflows.md#the-core-workflow)
2. [Commands: new-story](commands.md#agent-new-story-story_id)
3. [Commands: new-runbook](commands.md#agent-new-runbook-story_id)
4. [Commands: preflight](commands.md#agent-preflight-options)

### "I want to set up governance for my team"

1. [Governance System](governance.md)
2. [Configuration: agents.yaml](configuration.md#agentsyaml---governance-panel)
3. [Rules & Instructions](rules_and_instructions.md)
4. [Configuration: CI/CD Integration](configuration.md#cicd-integration)

### "I want to understand the AI features"

1. [AI Integration: Overview](ai_integration.md#supported-providers)
2. [AI Integration: Model Selection](ai_integration.md#model-selection)
3. [AI Integration: Token Management](ai_integration.md#token-management)
4. [Commands: AI Commands](commands.md#implementation)

### "I'm getting errors"

1. [Troubleshooting Guide](troubleshooting.md)
2. [Troubleshooting: Command Errors](troubleshooting.md#command-errors)
3. [Troubleshooting: AI Issues](troubleshooting.md#ai-issues)
4. [Troubleshooting: Preflight Issues](troubleshooting.md#preflight-issues)

### "I want to customize governance rules"

1. [Rules & Instructions: Overview](rules_and_instructions.md#overview)
2. [Governance: Adding New Rules](governance.md#customizing-governance)
3. [Rules: Creating Custom Rules](rules_and_instructions.md#creating-custom-rules)
4. [Rules: Role-Specific Instructions](rules_and_instructions.md#creating-role-specific-instructions)

## Reference Documentation

### Commands

| Command | Description | Documentation |
|---------|-------------|---------------|
| `new-story` | Create a story | [Link](commands.md#agent-new-story-story_id) |
| `new-plan` | Create a plan | [Link](commands.md#agent-new-plan-plan_id) |
| `new-runbook` | Generate runbook with AI | [Link](commands.md#agent-new-runbook-story_id) |
| `new-adr` | Create Architecture Decision Record | [Link](commands.md#agent-new-adr-title) |
| `implement` | AI-assisted implementation | [Link](commands.md#agent-implement-runbook_id) |
| `preflight` | Run governance checks | [Link](commands.md#agent-preflight-options) |
| `commit` | Governed commit | [Link](commands.md#agent-commit-options) |
| `pr` | Create pull request | [Link](commands.md#agent-pr-options) |
| `validate-story` | Validate story format | [Link](commands.md#agent-validate-story-story_id) |
| `match-story` | AI story matching | [Link](commands.md#agent-match-story---files-files) |
| `list-stories` | List all stories | [Link](commands.md#agent-list-stories) |
| `list-plans` | List all plans | [Link](commands.md#agent-list-plans) |
| `list-runbooks` | List all runbooks | [Link](commands.md#agent-list-runbooks) |

### Configuration Files

| File | Purpose | Documentation |
|------|---------|---------------|
| `agents.yaml` | Governance panel roles | [Link](configuration.md#agentsyaml---governance-panel) |
| `router.yaml` | AI model selection | [Link](configuration.md#routeryaml---offline-model-selection) |
| `.agent/rules/*.mdc` | Governance rules | [Link](rules_and_instructions.md#rules-directory-structure) |
| `.agent/instructions/` | Role instructions | [Link](rules_and_instructions.md#instructions-directory-structure) |
| `.agent/templates/` | File templates | [Link](configuration.md#template-configuration) |

### Governance Roles

| Role | Focus | Documentation |
|------|-------|---------------|
| Architect | System design, ADRs | [Link](governance.md#architect-reviews) |
| QA | Test coverage | [Link](governance.md#qa-reviews) |
| Security | Secrets, vulnerabilities | [Link](governance.md#security-reviews) |
| Product | Acceptance criteria | [Link](governance.md#product-reviews) |
| Docs | Documentation sync | [Link](governance.md#docs-reviews) |
| Compliance | SOC2, GDPR | [Link](governance.md#compliance-reviews) |
| Observability | Metrics, logging | [Link](governance.md#panel-members) |
| Mobile | React Native | [Link](governance.md#panel-members) |
| Web | Next.js, SEO | [Link](governance.md#panel-members) |
| Backend | FastAPI, Python | [Link](governance.md#panel-members) |

### File Structure

```
.agent/
├── bin/agent              # CLI executable
├── src/                   # Python implementation
│   ├── agent/
│   │   ├── commands/      # CLI commands
│   │   └── core/          # Core logic
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

## Additional Resources

### External Links

- [Google Gemini API](https://makersuite.google.com/app/apikey)
- [OpenAI Platform](https://platform.openai.com/api-keys)
- [GitHub CLI](https://cli.github.com/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [ADR Framework](https://adr.github.io/)

### Related Files

- `../CHANGELOG.md` - Version history
- `../GEMINI.md` - Agentic development instructions
- `../.agent/README.md` - Agent framework overview

## Getting Help

1. **Check documentation** - Use this index to find relevant guides
2. **Troubleshooting guide** - [Common issues](troubleshooting.md)
3. **GitHub Issues** - Report bugs or request features
4. **GitHub Discussions** - Ask questions, share ideas

---

**Ready to start?** → [Getting Started Guide](getting_started.md)
