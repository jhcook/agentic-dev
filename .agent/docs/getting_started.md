# Getting Started with Agent CLI

This guide will help you get up and running with the Agent CLI in less than 10 minutes.

## Prerequisites

- **Python 3.9+**
- **Git** (for repository management)
- **pip** (Python package manager)
- **ShellCheck** (for shell script linting)
- **Node.js & npm** (for JavaScript/TypeScript linting)
- Optional: API keys for AI providers (Gemini or OpenAI)

## Installation

### 1. Install Dependencies

```bash
# Navigate to your repository
cd /path/to/your/repo

# Install the agent package and its dependencies
pip install -e .agent/
```

The agent requires (automatically installed):
- `typer>=0.21.1` - CLI framework
- `rich>=14.2.0` - Terminal formatting
- `pydantic>=2.12.5` - Data validation
- `tiktoken>=0.12.0` - Token counting
- `google-genai>=1.57.0` - Google Gemini AI
- `openai>=2.15.0` - OpenAI API
- `PyYAML>=6.0.2` - Configuration parsing

### 2. Set Up AI Provider (Optional but Recommended)

Choose one of the following providers:

#### Option A: Google Gemini (Recommended)

```bash
export GEMINI_API_KEY="your-api-key-here"
# Or alternatively:
export GOOGLE_GEMINI_API_KEY="your-api-key-here"
```

**Get your API key**: [Google AI Studio](https://makersuite.google.com/app/apikey)

#### Option B: OpenAI

```bash
export OPENAI_API_KEY="your-api-key-here"
```

**Get your API key**: [OpenAI Platform](https://platform.openai.com/api-keys)

#### Option C: GitHub CLI (Fallback)

If you don't have an API key, Agent will use GitHub's AI models:

```bash
# Install GitHub CLI
brew install gh  # macOS
# or: sudo apt install gh  # Linux

# Authenticate
gh auth login
```

**Note**: GitHub CLI has a smaller context window (8k tokens) which may limit functionality on large files.

### 3. Test Installation

```bash
# Run from repository root
./.agent/bin/agent --version

# Or add to PATH
export PATH="$PATH:$(pwd)/.agent/bin"
agent --version
```

You should see output like:
```
Agent CLI v0.2.0
```

### 4. Verify AI Connection

Check that your AI provider is correctly configured and models are available:

```bash
agent list-models
```

## Your First Story

Let's create your first story using the agent:

### Step 1: Create a Story

```bash
agent new-story
```

You'll be prompted:
```
Select Story Category:
1. INFRA (Governance, CI/CD)
2. WEB (Frontend)
3. MOBILE (React Native)
4. BACKEND (FastAPI)

Choice: 2

Enter Story Title: Add user profile page
✅ Created Story: .agent/cache/stories/WEB/WEB-001-add-user-profile-page.md
```

### Step 2: Edit Your Story

Open the generated file and fill in the details:

```bash
# Open in your editor
vim .agent/cache/stories/WEB/WEB-001-add-user-profile-page.md
```

Key sections to complete:
- **Problem Statement**: What problem are we solving?
- **User Story**: As a [user], I want [capability] so that [value]
- **Acceptance Criteria**: Specific, testable conditions
- **Test Strategy**: How will we verify this works?

### Step 3: Update Story State

Change the state from `DRAFT` to `COMMITTED`:

```markdown
## State
COMMITTED
```

### Step 4: Generate a Runbook

```bash
agent new-runbook WEB-001
```

The AI will:
1. Read your story
2. Load governance rules
3. Generate a detailed implementation plan
4. Save to `.agent/cache/runbooks/WEB/WEB-001-runbook.md`

### Step 5: Review the Runbook

Open the generated runbook:

```bash
cat .agent/cache/runbooks/WEB/WEB-001-runbook.md
```

The runbook contains:
- **Goal description**
- **Compliance checklist** (what the governance panel will review)
- **Proposed changes** (files to create/modify)
- **Verification plan** (how to test)

### Step 6: Update Runbook State

Once you've reviewed the runbook, mark it as `ACCEPTED`:

```markdown
Status: ACCEPTED
```

### Step 7: Implement (Optional - AI Assisted)

```bash
agent implement WEB-001
```

The AI will:
1. Read the runbook
2. Generate code changes
3. Create/modify files according to the plan

## Running Preflight Checks

Before committing, always run preflight:

```bash
# Basic checks (lint, tests)
agent preflight --story WEB-001

# Full AI governance review
agent preflight --story WEB-001 --ai
```

The AI governance panel will review:
- ✅ Architecture compliance
- ✅ Security (no secrets/PII)
- ✅ Test coverage
- ✅ Documentation updates
- ✅ API contract validation
- ✅ Compliance requirements

## Committing Your Changes

### Option 1: Manual Commit

```bash
agent commit --story WEB-001
```

You'll be prompted to enter a conventional commit message:
```
feat(web): add user profile page component [WEB-001]
```

### Option 2: AI-Generated Commit

```bash
agent commit --story WEB-001 --ai
```

The AI will:
1. Analyze your staged changes
2. Generate a conventional commit message
3. Link to the story automatically

## Creating a Pull Request

```bash
# Run preflight and create PR
agent pr --story WEB-001

# Create draft PR
agent pr --story WEB-001 --draft

# Open PR in browser
agent pr --story WEB-001 --web
```

## Next Steps

Now that you've completed your first workflow, explore:

- **[Commands Reference](commands.md)** - Learn all available commands
- **[Governance System](governance.md)** - Understand the review process
- **[Workflows](workflows.md)** - Master story-driven development
- **[Configuration](configuration.md)** - Customize for your team

## Quick Tips

### 1. Use Tab Completion
```bash
# Add this to your ~/.zshrc or ~/.bashrc
eval "$(_AGENT_COMPLETE=zsh_source agent)"
```

### 2. Set Default Provider
```bash
# Always use Gemini
agent --provider gemini new-runbook WEB-001
```

### 3. Check Story Status
```bash
agent list-stories
```

### 4. Validate Before Committing
```bash
agent validate-story WEB-001
```

### 5. View Governance Logs
```bash
# Preflight logs are saved here
cat .agent/logs/preflight-*.log
```

## Troubleshooting

### "Story file not found"
Ensure your story exists and has the correct ID:
```bash
agent list-stories
```

### "AI returned empty response"
Check your API key is set:
```bash
echo $GEMINI_API_KEY
# Or
echo $OPENAI_API_KEY
```

### "Preflight failed"
Read the failure details carefully. Common issues:
- Missing test coverage
- No CHANGELOG entry
- Undocumented API changes
- Security violations

### "Command not found: agent"
Add to PATH or use full path:
```bash
export PATH="$PATH:$(pwd)/.agent/bin"
```

## Getting Help

```bash
# Show all commands
agent --help

# Get help for specific command
agent new-story --help
agent preflight --help
```

For more detailed help, see:
- [Commands Reference](commands.md)
- [Troubleshooting Guide](troubleshooting.md)
- GitHub Issues

---

**Next**: [Commands Reference](commands.md) →
