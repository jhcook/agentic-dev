# Commands Reference

Complete reference for all Agent CLI commands.

## Table of Contents

- [Story Management](#story-management)
- [Plan Management](#plan-management)
- [Runbook Management](#runbook-management)
- [Architecture Decisions](#architecture-decisions)
- [Implementation](#implementation)
- [Quality & Governance](#quality--governance)
- [Workflow Commands](#workflow-commands)
- [List & Query](#list--query)
- [Output Formats & Security](#output-formats--security)

---

## Story Management

### `agent new-story [STORY_ID]`

Create a new story file from an interactive template.

**Arguments:**
- `STORY_ID` (optional): Story ID like `WEB-001`. If omitted, you'll be prompted to select a category and an ID will be auto-assigned.

**Interactive Prompts:**
1. Select category (INFRA, WEB, MOBILE, BACKEND)
2. Enter story title
3. Auto-generated ID if not provided

**Output:**
- Creates `.agent/cache/stories/<SCOPE>/<STORY_ID>-<title>.md`
- Initial state: `DRAFT`

**Example:**
```bash
# Interactive mode
agent new-story

# With explicit ID
agent new-story WEB-015
```

**Story States:**
- `DRAFT` - Initial creation, being written
- `OPEN` - Ready for review
- `COMMITTED` - Locked, ready for runbook generation

### `agent validate-story <STORY_ID>`

Validate a story file's structure and required sections.

**Arguments:**
- `STORY_ID` (required): Story identifier like `INFRA-001`

**Checks:**
- ✅ All required sections present
- ✅ State is valid
- ✅ Acceptance criteria format
- ✅ Test strategy exists

**Example:**
```bash
agent validate-story WEB-001
```

**Exit Codes:**
- `0` - Validation passed
- `1` - Validation failed

---

## Plan Management

### `agent new-plan [PLAN_ID]`

Create a new high-level implementation plan manually from a template.

**Arguments:**
- `PLAN_ID` (optional): Plan ID like `INFRA-001`. If omitted, interactive selection.

**Interactive Prompts:**
1. Select category (INFRA, WEB, MOBILE, BACKEND)
2. Enter plan title
3. Auto-generated ID if not provided

**Output:**
- Creates `.agent/cache/plans/<SCOPE>/<PLAN_ID>-<title>.md`
- Initial state: `PROPOSED`

**Example:**
```bash
# Interactive mode
agent new-plan

# With explicit ID
agent new-plan BACKEND-003
```

**Plan States:**
- `PROPOSED` - Initial draft
- `APPROVED` - Reviewed and accepted, ready for stories

**Use Cases:**
- Creating high-level epics
- Organizing multiple related stories
- Architectural planning

---

## Runbook Management

### `agent new-runbook <STORY_ID>`

Generate a detailed implementation runbook using AI and the Governance Panel.

**Arguments:**
- `STORY_ID` (required): Story to generate runbook for (must be `COMMITTED`)

**Prerequisites:**
- Story must exist
- Story state must be `COMMITTED`
- AI provider configured (or GitHub CLI available)

**AI Process:**
1. Reads story content
2. Loads governance rules from `.agent/rules/`
3. Loads role-specific instructions from `.agent/instructions/`
4. Generates structured runbook
5. Runs through governance panel review

**Output:**
- Creates `.agent/cache/runbooks/<SCOPE>/<STORY_ID>-runbook.md`
- Initial state: `PROPOSED`

**Example:**
```bash
agent new-runbook WEB-001
```

**Runbook States:**
- `PROPOSED` - AI-generated, needs review
- `ACCEPTED` - Reviewed, ready for implementation

**Runbook Sections:**
- Goal description
- Compliance checklist
- Proposed changes (files to create/modify)
- Verification plan

### `agent list-runbooks`

List all runbooks in `.agent/cache/runbooks/`.

**Options:**
- `--format <format>` - Output format (pretty, json, yaml, csv, tsv, markdown, plain)
- `--output <file>` - Write to file instead of stdout

**Example:**
```bash
agent list-runbooks
agent list-runbooks --format json --output runbooks.json
```

---

## Architecture Decisions

### `agent new-adr [TITLE]`

Create a new Architecture Decision Record (ADR).

**Arguments:**
- `TITLE` (optional): ADR title. If omitted, you'll be prompted.

**Interactive Prompts:**
1. Enter ADR title
2. Auto-assigned ADR number

**Output:**
- Creates `.agent/adrs/ADR-<NUM>-<title>.md`
- Initial state: `PROPOSED`

**Example:**
```bash
# Interactive mode
agent new-adr

# With title
agent new-adr "Use PostgreSQL for primary database"
```

**ADR Template Sections:**
- Status (PROPOSED, ACCEPTED, DEPRECATED, SUPERSEDED)
- Context
- Decision
- Consequences
- Alternatives considered

**Best Practices:**
- Create ADRs for significant architectural decisions
- Link ADRs in stories (use `## Linked ADRs` section)
- Update ADR status when decision changes

---

## Implementation

### `agent implement <RUNBOOK_ID>`

Execute an implementation runbook using AI assistance.

**Arguments:**
- `RUNBOOK_ID` (required): Runbook to implement (must be `ACCEPTED`)

**Prerequisites:**
- Runbook must exist
- Runbook state must be `ACCEPTED`
- AI provider configured

**AI Process:**
1. Reads runbook content
2. Interprets proposed changes
3. Generates code for each file
4. Creates/modifies files according to plan
5. Runs verification steps

**Example:**
```bash
agent implement WEB-001
```

**Safety Features:**
- Shows diff before making changes
- Requires confirmation for destructive operations
- Creates backup of modified files

**Limitations:**
- AI may not perfectly understand complex logic
- Always review generated code
- Run tests after implementation

---

## Quality & Governance

### `agent preflight [OPTIONS]`

Run comprehensive preflight checks before committing.

**Options:**
- `--story <STORY_ID>` - Associate with specific story
- `--ai` - Run full AI governance panel review
- `--base <BRANCH>` - Compare against specific branch (default: `main`)
- `--provider <PROVIDER>` - Force AI provider (gh, gemini, openai)

**Checks Performed:**

#### Basic Checks (Always)
- ✅ Git status (no uncommitted changes in critical files)
- ✅ Linting (if configured)
- ✅ Tests (if test suite exists)

#### AI Checks (with `--ai`)
- 🤖 **@Architect**: ADR compliance, architectural boundaries
- 🤖 **@Security**: Secrets scanning, PII detection, vulnerabilities
- 🤖 **@QA**: Test coverage, test strategy validation
- 🤖 **@Product**: Acceptance criteria, impact analysis
- 🤖 **@Observability**: OpenTelemetry instrumentation, logging
- 🤖 **@Docs**: Documentation updates, CHANGELOG, API docs
- 🤖 **@Compliance**: SOC2, GDPR enforcement
- 🤖 **@Mobile**: React Native patterns (if applicable)
- 🤖 **@Web**: Next.js conventions, SEO (if applicable)
- 🤖 **@Backend**: FastAPI patterns, types (if applicable)

**Example:**
```bash
# Basic preflight
agent preflight --story WEB-001

# Full governance review
agent preflight --story WEB-001 --ai

# Against feature branch
agent preflight --story WEB-001 --ai --base develop

# Force specific provider
agent preflight --story WEB-001 --ai --provider gemini
```

**Output:**
- Console report with pass/fail status
- Detailed log saved to `.agent/logs/preflight-<timestamp>.log`

**Exit Codes:**
- `0` - All checks passed
- `1` - One or more checks failed

### `agent impact <STORY_ID>`

Run impact analysis for a story.

**Arguments:**
- `STORY_ID` (required): Story to analyze

**Analysis:**
- Files that will be modified
- Dependent components
- Test coverage impact
- Risk assessment

**Example:**
```bash
agent impact WEB-001
```

### `agent panel <STORY_ID>`

Simulate a governance panel review (interactive).

**Arguments:**
- `STORY_ID` (required): Story to review

**Process:**
1. Loads story content
2. Convenes virtual panel
3. Each role provides feedback
4. Generates consensus report

**Example:**
```bash
agent panel WEB-001
```

### `agent run-ui-tests <STORY_ID>`

Run UI journey tests for a story.

**Arguments:**
- `STORY_ID` (required): Story to test

**Example:**
```bash
agent run-ui-tests WEB-001
```

---

## Workflow Commands

### `agent commit [OPTIONS]`

Commit changes with governed message format.

**Options:**
- `--story <STORY_ID>` - Link commit to story
- `--runbook <RUNBOOK_ID>` - Link commit to runbook
- `--ai` - AI-generate commit message from staged diff

**Commit Message Format (Conventional Commits):**
```
<type>(<scope>): <description> [<STORY_ID>]

<body>

<footer>
```

**Types:** feat, fix, docs, style, refactor, test, chore

**Interactive Prompts:**
1. Select commit type
2. Enter scope (component affected)
3. Enter description
4. Optional body
5. Story ID auto-appended

**Example:**
```bash
# Manual commit
agent commit --story WEB-001

# AI-generated message
agent commit --story WEB-001 --ai

# With runbook link
agent commit --runbook WEB-001 --story WEB-001
```

**AI Commit Generation:**
- Analyzes staged diff
- Infers appropriate type and scope
- Generates concise, conventional message
- Links to story automatically

### `agent pr [OPTIONS]`

Create a GitHub Pull Request for the current branch.

**Options:**
- `--story <STORY_ID>` - Link PR to story
- `--web` - Open PR in browser after creation
- `--draft` - Create as draft PR

**Process:**
1. Runs preflight checks
2. Generates PR title from story
3. Generates PR body with:
   - Story summary
   - Acceptance criteria checklist
   - Test verification steps
   - Governance report
4. Creates PR via GitHub CLI

**Prerequisites:**
- GitHub CLI installed (`gh`)
- Authenticated (`gh auth login`)
- On a feature branch (not main)
- All changes committed

**Example:**
```bash
# Basic PR
agent pr --story WEB-001

# Draft PR
agent pr --story WEB-001 --draft

# Open in browser
agent pr --story WEB-001 --web
```

**PR Template Sections:**
- Story link
- Changes summary
- Acceptance criteria checklist
- Screenshots (if applicable)
- Breaking changes
- Migration steps

### `agent match-story --files <FILES>`

AI-assisted story selection based on changed files.

**Options:**
- `--files <FILES>` (required): Space-separated list of files

**Process:**
1. Analyzes file paths and content
2. Loads all existing stories
3. Uses AI to match files to most relevant story
4. Returns story ID and confidence score

**Example:**
```bash
agent match-story --files "src/components/Button.tsx src/styles/button.css"

# From git diff
agent match-story --files "$(git diff --name-only)"
```

**Use Cases:**
- Automatic story inference in `commit --ai`
- CI/CD pipeline story detection
- Validating commit-story linkage

---

## List & Query

### `agent list-stories`

List all stories in `.agent/cache/stories/`.

**Options:**
- `--format <format>` - Output format (pretty, json, yaml, csv, tsv, markdown, plain)
- `--output <file>` - Write to file instead of stdout
- `--scope <scope>` - Filter by scope (INFRA, WEB, MOBILE, BACKEND)
- `--state <state>` - Filter by state (DRAFT, OPEN, COMMITTED)

**Example:**
```bash
# Default table view
agent list-stories

# JSON output
agent list-stories --format json

# Filter by scope
agent list-stories --scope WEB

# Export to file
agent list-stories --format csv --output stories.csv
```

**Output Columns:**
- Story ID
- Title
- State
- Scope
- Created date

### `agent list-plans`

List all plans in `.agent/cache/plans/`.

**Options:**
- `--format <format>` - Output format (pretty, json, yaml, csv, tsv, markdown, plain)
- `--output <file>` - Write to file instead of stdout

**Example:**
```bash
agent list-plans
agent list-plans --format json
```

---

## Global Options

These options work with any command:

### `--provider <PROVIDER>`

Force a specific AI provider.

**Values:**
- `gemini` - Google Gemini (gemini-1.5-pro)
- `openai` - OpenAI (gpt-4o)
- `gh` - GitHub CLI models

**Example:**
```bash
agent --provider gemini new-runbook WEB-001
agent --provider openai preflight --story WEB-001 --ai
```

### `--version`

Show Agent CLI version.

**Example:**
```bash
agent --version
# Output: Agent CLI v0.2.0
```

### `--help`

Show help message.

**Example:**
```bash
# General help
agent --help

# Command-specific help
agent new-story --help
agent preflight --help
```

---

## Environment Variables

### AI Provider Keys

```bash
# Google Gemini
export GEMINI_API_KEY="your-key"
# Or
export GOOGLE_GEMINI_API_KEY="your-key"

# OpenAI
export OPENAI_API_KEY="your-key"
```

### Configuration

```bash
# Custom agent directory (default: .agent)
export AGENT_DIR="/path/to/custom/agent"

# Default AI provider
export AGENT_DEFAULT_PROVIDER="gemini"

# Log level
export AGENT_LOG_LEVEL="DEBUG"  # DEBUG, INFO, WARNING, ERROR
```

---

## Distributed Synchronization

### `agent sync scan`
Ingest existing artifacts (Stories, Plans, Runbooks, ADRs) from the file system into the local SQLite cache.

**Prerequisites:**
- Run `python .agent/src/agent/db/init.py` (only needed once for initial setup).

**What it does:**
- Scans `.agent/cache/` for Stories, Plans, Runbooks.
- Scans `.agent/adrs/` for ADRs.
- Parses ID, Type, Content, and State (from headers or metadata).
- Upserts them into `.agent/cache/agent.db`.
- Extracts and creates links between artifacts (Plan->Story, Story->ADR).

**Example:**
```bash
agent sync scan
```

### `agent sync status`
Show the current state of the local artifact database.

**Output:**
- Table showing ID, Type, Version, and State of all indexed artifacts.

**Example:**
```bash
agent sync status
```

### `agent sync delete <ID> [--type <TYPE>]`
Remove an artifact from the local database.

**Arguments:**
- `ID`: The artifact ID (e.g., `INFRA-001`).
- `--type` (optional): `story`, `runbook`, `plan`, `adr`. If omitted, deletes ALL artifacts with that ID (e.g. both Story and Runbook).

**Example:**
```bash
# Delete all artifacts with ID INFRA-999
agent sync delete INFRA-999

# Delete only the runbook
agent sync delete INFRA-004 --type runbook
```

---

## Exit Codes

All commands follow standard Unix exit code conventions:

- `0` - Success
- `1` - General error (command failed)
- `2` - Usage error (invalid arguments)

---

## Examples: Complete Workflows

### Creating a New Feature

```bash
# 1. Create story
agent new-story
# Select: 2 (WEB)
# Title: "Add user profile page"
# Creates: WEB-001

# 2. Edit story (add details)
vim .agent/cache/stories/WEB/WEB-001-add-user-profile-page.md
# Update State to: COMMITTED

# 3. Generate runbook
agent new-runbook WEB-001

# 4. Review & accept runbook
vim .agent/cache/runbooks/WEB/WEB-001-runbook.md
# Update Status to: ACCEPTED

# 5. Implement (AI-assisted)
agent implement WEB-001

# 6. Review generated code
git diff

# 7. Run preflight
agent preflight --story WEB-001 --ai

# 8. Commit
agent commit --story WEB-001 --ai

# 9. Create PR
agent pr --story WEB-001 --web
```

### Fixing a Bug

```bash
# 1. Create bug story
agent new-story
# Select: 4 (BACKEND)
# Title: "Fix authentication timeout"
# Creates: BACKEND-042

# 2. Make fixes
# ... edit code ...

# 3. Run preflight
agent preflight --story BACKEND-042

# 4. Commit
agent commit --story BACKEND-042
# Type: fix
# Scope: auth
# Description: increase timeout to 30s

# 5. Create PR
agent pr --story BACKEND-042
```

---

**Next**: [Governance System](governance.md) →

## Output Formats & Security

All list commands support multiple output formats via the `--format` flag.

### Supported Formats

| Format | Description | Use Case |
|--------|-------------|----------|
| **pretty** | Rich text tables (Default) | Human readability in terminal |
| **json** | JSON array of objects | Programmatic processing (jq) |
| **csv** | Comma-separated values | Spreadsheets, legacy tools |
| **tsv** | Tab-separated values | Spreadsheets, strict parsing |
| **yaml** | YAML list | Configuration generation |
| **markdown** | Markdown table | Documentation embedding |
| **plain** | Tab-separated text | Simple grep/awk processing |

### JSON Example
```bash
agent list-stories --format json
# Output:
# [
#   {
#     "ID": "WEB-001",
#     "Title": "Add login",
#     "State": "COMMITTED",
#     "Path": ".agent/cache/stories/WEB/WEB-001.md"
#   }
# ]
```

### Security & Compliance

**PII Scrubbing**: All output formats are automatically scrubbed for Personally Identifiable Information (PII) such as emails, IP addresses, and API keys. This ensures that exporting data to external files or tools does not leak sensitive information.

**CSV Injection Prevention**: When exporting to CSV or TSV, fields starting with special characters (=, +, -, @) are escaped with a single quote (') to prevent formula injection attacks in spreadsheet software (Excel, Google Sheets).
