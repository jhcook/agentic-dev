# Workflows Guide

Master the story-driven development process with Agent CLI.

## Overview

Agent enforces a structured workflow that ensures quality at every step:

```
Plan → Story → Runbook → Implementation → Review → Merge
```

## The Core Workflow

### 1. Planning Phase

#### Creating a Plan (Optional for Epics)

```bash
agent new-plan
```

**When to create a plan:**
- Multi-story feature (epic)
- Cross-team coordination needed
- Architectural changes

**Plan states:**
- `PROPOSED` → Under discussion
- `APPROVED` → Ready for story creation

### 2. Story Creation

```bash
agent new-story
```

**Interactive prompts:**
1. Select scope (INFRA/WEB/MOBILE/BACKEND)
2. Enter title
3. Get auto-assigned ID (e.g., WEB-042)

**Edit the story:**
```bash
vim .agent/cache/stories/WEB/WEB-042-feature-name.md
```

**Required sections:**
- Problem Statement
- User Story  
- Acceptance Criteria (testable!)
- Test Strategy
- Rollback Plan

**Story states:**
- `DRAFT` → Being written
- `OPEN` → Ready for review
- `COMMITTED` → Locked, ready for runbook

**Change state when ready:**
```markdown
## State
COMMITTED
```

### 3. Runbook Generation

```bash
agent new-runbook WEB-042
```

**Prerequisites:**
- Story must be `COMMITTED`

**AI generates:**
- Implementation steps
- Files to create/modify
- Compliance checklist
- Verification plan

**Review & accept:**
```bash
vim .agent/cache/runbooks/WEB/WEB-042-runbook.md
```

Change status to:
```markdown
Status: ACCEPTED
```

### 4. Implementation

#### Option A: Manual Implementation

```bash
# Just code it yourself
vim src/features/new-feature.ts
```

#### Option B: AI-Assisted

```bash
agent implement WEB-042
```

AI will:
- Read runbook
- Generate code
- Create/modify files
- Run verification

**Always review AI-generated code!**

### 5. Testing & Validation

```bash
# Run tests
npm test  # or pytest, etc.

# Run preflight
agent preflight --story WEB-042
```

Basic preflight checks:
- Linting
- Tests pass
- No uncommitted changes

### 6. Governance Review

```bash
agent preflight --story WEB-042 --ai
```

Full AI governance panel:
- @Architect - Design patterns
- @Security - Vulnerabilities
- @QA - Test coverage
- @Product - Acceptance criteria
- @Docs - Documentation
- @Compliance - SOC2/GDPR
- + scope-specific (Mobile/Web/Backend)

**Fix any blockers before committing!**

### 7. Commit

```bash
# Stage changes
git add .

# Commit with governance
agent commit --story WEB-042

# Or AI-generated message
agent commit --story WEB-042 --ai
```

Commit format:
```
feat(web): add user profile page [WEB-042]

- Implements avatar upload
- Adds bio editing
- Includes unit tests
```

### 8. Pull Request

```bash
agent pr --story WEB-042
```

Creates PR with:
- Story summary
- Acceptance criteria checklist
- Governance report
- Test verification

**Options:**
```bash
# Draft PR
agent pr --story WEB-042 --draft

# Open in browser
agent pr --story WEB-042 --web
```

### 9. Review & Merge

Team reviews PR:
- Code quality
- Test coverage
- Documentation
- Governance feedback

Merge when approved ✅

## Workflow Variations

### Bug Fix Workflow

```bash
# 1. Create bug story
agent new-story
# Scope: Backend
# Title: "Fix authentication timeout"

# 2. Mark as COMMITTED (skip runbook for simple fixes)
vim .agent/cache/stories/BACKEND-042-fix-auth-timeout.md

# 3. Fix the bug
vim src/auth/middleware.py

# 4. Test
pytest tests/auth/

# 5. Preflight
agent preflight --story BACKEND-042

# 6. Commit
agent commit --story BACKEND-042
# Type: fix
# Description: "increase timeout to 30s"

# 7. PR
agent pr --story BACKEND-042
```

### Hotfix Workflow

```bash
# 1. Create from main
git checkout -b hotfix/BACKEND-099-critical-security-fix

# 2. Minimal story (can skip in emergencies)
echo "# BACKEND-099: Critical Security Fix" > \
  .agent/cache/stories/BACKEND/BACKEND-099-security-fix.md

# 3. Make fix
vim src/auth/validator.py

# 4. Basic preflight only
agent preflight --story BACKEND-099

# 5. Fast-track commit
git commit -m "fix(auth): patch SQL injection [BACKEND-099]"

# 6. Emergency PR
gh pr create --title "Hotfix: SQL Injection" --body "BACKEND-099" --web

# 7. Post-mortem story
# After merge, create proper story retroactively
```

### Documentation-Only Workflow

```bash
# 1. Create docs story
agent new-story
# Scope: INFRA
# Title: "Update API documentation"

# 2. Update docs
vim docs/api/README.md
vim docs/openapi.yaml

# 3. Light preflight
agent preflight --story INFRA-050

# 4. Commit
agent commit --story INFRA-050
# Type: docs

# 5. PR
agent pr --story INFRA-050
```

## Advanced Workflows

### Multi-Story Feature

```bash
# 1. Create plan
agent new-plan
# ID: WEB-PLAN-001
# Title: "User Dashboard Redesign"

# 2. Create stories under plan
agent new-story  # WEB-100: Navigation component
agent new-story  # WEB-101: Widgets system
agent new-story  # WEB-102: Settings panel

# 3. Work on stories in parallel
# Team member A: WEB-100
# Team member B: WEB-101
# Team member C: WEB-102

# 4. Each story follows standard workflow
agent new-runbook WEB-100
agent implement WEB-100
# ... etc
```

### Refactoring Workflow

```bash
# 1. Create refactoring story
agent new-story
# Scope: BACKEND
# Title: "Extract payment processing to service"

# 2. Create detailed runbook
agent new-runbook BACKEND-080

# Review runbook for:
# - Files to modify
# - Tests to update
# - Migration path

# 3. Implement incrementally
git checkout -b refactor/BACKEND-080

# 3a. Step 1: Extract interface
git commit -m "refactor(payment): extract interface [BACKEND-080]"

# 3b. Step 2: Implement service
git commit -m "refactor(payment): implement service [BACKEND-080]"

# 3c. Step 3: Migrate callers
git commit -m "refactor(payment): migrate to service [BACKEND-080]"

# 4. Verify no regression
pytest tests/payment/

# 5. Full governance review
agent preflight --story BACKEND-080 --ai

# 6. PR
agent pr --story BACKEND-080
```

## Story State Management

### State Transitions

```
DRAFT → Can edit freely
  ↓
OPEN → Ready for team review
  ↓
COMMITTED → Locked, ready for runbook generation
```

**Never skip states!**

### Reopening a Story

If requirements change after `COMMITTED`:

```bash
# 1. Revert to OPEN
vim .agent/cache/stories/WEB/WEB-042-feature.md
# Change: State: OPEN

# 2. Update requirements

# 3. Reconvene governance panel
agent panel WEB-042

# 4. Re-commit when stable
# Change: State: COMMITTED
```

## Workflow Automation

### Git Hooks

**.git/hooks/pre-commit:**
```bash
#!/bin/bash
# Auto-run preflight before commit

# Extract story from branch name
STORY=$(git branch --show-current | grep -oE '[A-Z]+-[0-9]+')

if [ -n "$STORY" ]; then
  .agent/bin/agent preflight --story $STORY
  exit $?
fi
```

### Aliases

**~/.zshrc:**
```bash
# Story workflow shortcuts
alias story='agent new-story'
alias runbook='agent new-runbook'
alias implement='agent implement'
alias prefly='agent preflight --ai'
alias acommit='agent commit --ai'
alias apr='agent pr --web'
```

Usage:
```bash
story          # Create new story
runbook WEB-42 # Generate runbook
implement WEB-42
prefly --story WEB-42
acommit --story WEB-42
apr --story WEB-42
```

## Best Practices

### 1. Write Testable Acceptance Criteria

**❌ Bad:**
```markdown
- [ ] User can edit profile
```

**✅ Good:**
```markdown
- [ ] Given logged-in user, When clicks "Edit Profile", Then sees editable form
- [ ] Given edited profile, When clicks "Save", Then changes persist
- [ ] Given invalid email, When clicks "Save", Then sees error message
```

### 2. Link Related Stories

```markdown
## Dependencies
- Depends on: WEB-040 (Authentication)
- Blocks: WEB-045 (Admin Dashboard)
- Related: MOBILE-023 (Mobile Profile)
```

### 3. Keep Stories Small

**One story = One PR**

If story balloons, split it:
```bash
# Original
WEB-042: User profile page

# Split into:
WEB-042: User profile - View mode
WEB-043: User profile - Edit mode  
WEB-044: User profile - Avatar upload
```

### 4. Use Conventional Commits

**Types:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `refactor:` Code restructure
- `test:` Test additions
- `chore:` Maintenance

**Scopes:**
- `web`, `mobile`, `backend`, `infra`
- Or component: `auth`, `payment`, `api`

### 5. Run Preflight Often

Don't wait until the end:
```bash
# After major change
git add .
agent preflight --story WEB-042

# Before breaking for lunch
agent preflight --story WEB-042

# Before creating PR
agent preflight --story WEB-042 --ai
```

---

**Next**: [AI Integration](ai_integration.md) →
