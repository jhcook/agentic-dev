# Configuration Guide

Learn how to configure and customize the Agent CLI for your team.

## Configuration Files

The Agent CLI uses several configuration files:

```
.agent/etc/
├── agents.yaml          # Governance panel roles
└── router.yaml          # AI model routing rules
```

## agents.yaml - Governance Panel

Defines the roles in your governance panel.

### Structure

```yaml
team:
  - role: architect             # Unique role identifier
    name: "System Architect"    # Human-readable name
    description: "..."          # Role description
    responsibilities:           # List of duties
      - "Review and approve ADRs"
      - "Enforce architectural boundaries"
    governance_checks:          # Specific validations
      - "Do ADRs exist for major changes?"
      - "Are architectural boundaries respected?"
    instruction: "..."          # Where to find additional context
```

### Adding a Custom Role

Example: Adding a DevOps role

```yaml
team:
  - role: devops
    name: "DevOps Engineer"
    description: "Infrastructure and CI/CD expert"
    responsibilities:
      - "Review deployment scripts"
      - "Validate infrastructure as code"
      - "Ensure monitoring and alerting"
    governance_checks:
      - "Are deployment scripts tested?"
      - "Is rollback procedure documented?"
      - "Are health checks configured?"
    instruction: "Consult .agent/instructions/devops/ for checklists"
```

Create corresponding instructions:

```bash
mkdir -p .agent/instructions/devops
cat > .agent/instructions/devops/deployment-safety.md << 'EOF'
# Deployment Safety Checklist

- [ ] Blue-green deployment or canary release
- [ ] Database migrations backward-compatible
- [ ] Rollback tested
- [ ] Monitoring dashboard ready
- [ ] Incident response plan updated
EOF
```

### Modifying Existing Roles

To change a role's focus, edit `.agent/etc/agents.yaml`:

```yaml
  - role: security
    name: "Security & Compliance Officer"
    responsibilities:
      - "Scan for secrets and PII"
      - "Verify GDPR/SOCI2 compliance"
      - "Review dependency vulnerabilities"
      - "Audit authentication/authorization"  # Added
    governance_checks:
      - "No PII in logs"
      - "No secrets in code"
      - "Compliance docs checked"
      - "Auth follows ADR-007"  # Added
```

### Disabling Roles

To temporarily disable a role, comment it out:

```yaml
team:
  # - role: mobile
  #   name: "Mobile Lead"
  #   ...
```

Or remove it entirely.

## router.yaml - AI Model Selection

Controls which AI model is used for different tasks.

### Structure

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

  gpt-4o-mini:
    provider: openai
    tier: light
    context_window: 128000
    cost_per_1k_input: 0.00015

settings:
  default_tier: standard
  provider_priority:
    - gemini
    - openai
    - gh
    - anthropic
```

### Customizing Model Selection

#### Use Cheaper Models for Simple Tasks

```yaml
tiers:
  tier1:
    models:
      - "gemini-1.5-pro"
    use_cases:
      - "runbook generation"
      - "governance panel review"
  
  tier2:
    models:
      - "gemini-1.5-flash"  # Faster, cheaper
    cost_per_1m_tokens: 0.075
    use_cases:
      - "commit message generation"
      - "story matching"
      - "simple validation"

default_tier: tier2  # Changed: use cheaper tier by default
```

#### Add Custom Model

```yaml
tiers:
  tier1:
    models:
      - "claude-3-opus"  # Anthropic Claude
    context_window: 200000
    cost_per_1m_tokens: 15.00
    use_cases:
      - "complex architectural reviews"
```

Then set up the provider:

```python
# .agent/src/agent/core/ai/service.py
from anthropic import Anthropic

class AIService:
    def _try_complete(self, provider, system, user, model=None):
        if provider == "anthropic":
            client = self.clients['anthropic']
            # ...

```

### Routing Logic

The router selects models based on:

1. **Context size** - Amount of text to analyze
2. **Task type** - Defined in `use_cases`
3. **Provider availability** - API keys set
4. **Cost optimization** - Lower tier if sufficient

Override with `--provider` flag:

```bash
agent --provider gemini new-runbook WEB-001
```

## Environment Variables

### AI Provider Keys

```bash
# Google Gemini (recommended)
export GEMINI_API_KEY="AIza..."
# Or
export GEMINI_API_KEY="AIza..."

# OpenAI
export OPENAI_API_KEY="sk-..."

# Anthropic (if configured)
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Tip**: Verify your keys and view available models:

```bash
agent list-models
agent list-models anthropic
```

### Agent Configuration

```bash
# Custom agent directory (default: .agent)
export AGENT_DIR="/path/to/custom/.agent"

# Default AI provider
export AGENT_DEFAULT_PROVIDER="gemini"  # or "openai", "gh"

# Log level
export AGENT_LOG_LEVEL="DEBUG"  # DEBUG, INFO, WARNING, ERROR

# Chunk size for large diffs (default: 6000 chars)
export AGENT_CHUNK_SIZE="8000"

# Preflight output directory
export AGENT_LOG_DIR=".agent/logs"
```

### Adding to Shell Profile

```bash
# Add to ~/.zshrc or ~/.bashrc
cat >> ~/.zshrc << 'EOF'
# Agent CLI Configuration
export GEMINI_API_KEY="your-key-here"
export AGENT_LOG_LEVEL="INFO"
export PATH="$PATH:$HOME/your-repo/.agent/bin"
EOF

source ~/.zshrc
```

## Directory Structure Configuration

### Default Structure

```
.agent/
├── bin/              # Executables
├── src/              # Python source
├── cache/            # Generated artifacts
│   ├── stories/      # Story files
│   ├── plans/        # Plan files
│   └── runbooks/     # Runbook files
├── templates/        # Templates
├── rules/            # Governance rules
├── instructions/     # Role instructions
├── compliance/       # SOC2, GDPR docs
├── workflows/        # Workflow definitions
├── etc/              # Configuration files
└── logs/             # Preflight logs
```

### Customizing Paths

Edit `.agent/src/agent/core/config.py`:

```python
from pathlib import Path
import os

class Config:
    def __init__(self):
        self.root = Path(os.environ.get('AGENT_DIR', '.agent'))
        
        # Customize these paths
        self.cache_dir = self.root / 'cache'
        self.stories_dir = self.cache_dir / 'stories'
        self.plans_dir = self.cache_dir / 'plans'
        self.runbooks_dir = self.cache_dir / 'runbooks'
        
        # Custom template location
        self.templates_dir = self.root / 'custom-templates'
        
        # Custom rules location
        self.rules_dir = self.root / 'governance-rules'
        
        # Custom logs location
        self.logs_dir = Path('/var/log/agent')
```

## Template Configuration

### Story Template

Edit `.agent/templates/story-template.md`:

```markdown
# STORY-XXX: Title

## State
DRAFT

## Problem Statement
What problem are we solving?

## User Story
As a <user>, I want <capability> so that <value>.

## Acceptance Criteria
- [ ] **Scenario 1**: Given <context>, When <action>, Then <result>.
- [ ] **Scenario 2**: <Condition> must be met.

## Business Value
<!-- Add custom section -->
**Impact**: High | Medium | Low
**Effort**: High | Medium | Low

## Technical Approach
<!-- Add custom section -->
Brief description of how this will be implemented.

## Dependencies
<!-- Add custom section -->
- Depends on: STORY-XXX
- Blocks: STORY-YYY

## Test Strategy
How will we verify correctness?

## Rollback Plan
How do we revert safely?
```

### Runbook Template

Edit `.agent/templates/runbook-template.md`:

```markdown
# {{STORY_ID}}: {{TITLE}}

Status: PROPOSED

## Goal
{{AI_GENERATED_SUMMARY}}

## Compliance Checklist
- [ ] @Architect: Architectural review
- [ ] @Security: Security scan
- [ ] @QA: Test strategy approved

## Timeline
**Estimated Effort**: {{AI_ESTIMATE}}
**Deadline**: {{DEADLINE}}

## Implementation Steps

### Phase 1: Setup
{{AI_GENERATED_STEPS}}

### Phase 2: Core Implementation
{{AI_GENERATED_STEPS}}

### Phase 3: Testing
{{AI_GENERATED_STEPS}}

### Phase 4: Documentation
{{AI_GENERATED_STEPS}}

## Rollback Procedure
{{AI_GENERATED_ROLLBACK}}
```

## Workflow Configuration

Workflows are defined in `.agent/workflows/*.md`.

### Creating a Custom Workflow

Example: Code review workflow

```bash
cat > .agent/workflows/code-review.md << 'EOF'
---
description: Conduct thorough code review
---

# Code Review Workflow

## Prerequisites
- [ ] Pull request created
- [ ] CI/CD pipeline green
- [ ] Story linked to PR

## Steps

1. **Checkout PR branch**
   ```bash
   gh pr checkout <PR_NUMBER>
   ```

1. **Run local preflight**

   ```bash
   agent preflight --story <STORY_ID>
   ```

2. **Review code changes**

   ```bash
   git diff main...HEAD
   ```

3. **Check test coverage**

   ```bash
   pytest --cov=src tests/
   ```

4. **Approve or request changes**

   ```bash
   gh pr review --approve
   # Or
   gh pr review --request-changes -b "Comments..."
   ```

## Checklist

- [ ] Code follows style guide
- [ ] Tests added for new functionality
- [ ] Documentation updated
- [ ] No security issues
- [ ] Performance acceptable
EOF

```

Use the workflow:

```bash
# Reference in documentation
# Or create a slash command:
alias review="cat .agent/workflows/code-review.md"
```

## CI/CD Integration

### GitHub Actions

`.github/workflows/agent-preflight.yml`:

```yaml
name: Agent Preflight

on:
  pull_request:
    branches: [main, develop]

jobs:
  preflight:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -e .agent/
      
      - name: Run preflight checks
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: |
          # Extract story ID from branch name
          STORY_ID=$(echo ${{ github.head_ref }} | grep -oE '[A-Z]+-[0-9]+')
          
          if [ -n "$STORY_ID" ]; then
            .agent/bin/agent preflight --story $STORY_ID
          else
            .agent/bin/agent preflight
          fi
      
      - name: Upload logs
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: preflight-logs
          path: .agent/logs/
```

### GitLab CI

`.gitlab-ci.yml`:

```yaml
preflight:
  stage: test
  image: python:3.11
  script:
    # Install in editable mode
    - pip install -e .agent/
    # Install with Optional Capabilities
    # pip install -e ".agent/[voice]" # Conversational Agent
    # pip install -e ".agent/[admin]" # Admin Console
    - export STORY_ID=$(echo $CI_COMMIT_REF_NAME | grep -oE '[A-Z]+-[0-9]+')
    - .agent/bin/agent preflight --story $STORY_ID
  artifacts:
    when: always
    paths:
      - .agent/logs/
  only:
    - merge_requests
```

## Team-Specific Customization

### Startup Company

Lean governance, focus on speed:

```yaml
# .agent/etc/agents.yaml - Minimal panel
team:
  - role: security
    # ... (essential)
  - role: qa
    # ... (essential)
```

```bash
# Simpler rules
mv .agent/rules/detailed/*.mdc .agent/rules/archive/
```

### Enterprise

Comprehensive governance, compliance-heavy:

```yaml
# .agent/etc/agents.yaml - Full panel
team:
  - role: architect
  - role: qa
  - role: security
  - role: compliance
  - role: product
  - role: docs
  - role: observability
  - role: legal  # Added
  - role: data-privacy  # Added
```

```bash
# More detailed rules
cp enterprise-rules/*.mdc .agent/rules/
```

## Best Practices

1. **Version control all config** - Commit `.agent/etc/*`
2. **Document changes** - Add CHANGELOG entry for governance changes
3. **Test before deploying** - Run preflight on sample code
4. **Gradual rollout** - Start with WARNING severity, upgrade to BLOCKER
5. **Team consensus** - Review config changes in PRs

---

**Next**: [AI Integration](ai_integration.md) →
