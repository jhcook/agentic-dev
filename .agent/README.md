# Agent Governance Framework

This directory contains the governance framework for the `inspected-app` monorepo. It is designed to ensure strict adherence to architectural standards, compliance (SOC2/GDPR), and quality assurance through a "Governance by Code" approach.

## Core Concepts

### 1. The "Agent" CLI
The `agent` CLI (`.agent/bin/agent`) is the primary interface for this framework. It automates:
*   **Creation**: Scaffolding new Stories, ADRs, and Plans.
*   **Validation**: Checking content against schemas.
*   **Preflight**: Running heuristics (compliance, security, arch) before you commit.
*   **Governance Panel**: Simulating a multi-role review (Architect, QA, Security, Product, SRE).

### 2. Workflow
We follow a strict **Story-Driven Development** workflow:

1.  **Plan (Optional)**: `agent new-plan` for complex Epics breaking down into multiple stories.
2.  **Draft a Story**: `agent new-story` (Prompts for logical category: INFRA, WEB, MOBILE, BACKEND).
3.  **Draft a Runbook**: `agent new-runbook` (Prompts for logical category: INFRA, WEB, MOBILE, BACKEND).
4.  **Implement**: `agent implement --story WEB-123` (Prompts for logical category: INFRA, WEB, MOBILE, BACKEND).
5.  **Preflight**: `agent preflight --story WEB-123` (Must pass before commit).
6.  **Commit**: `agent commit --story WEB-123` (Enforces commit message standards).

### 3. Governance States
To proceed with any code changes or architectural updates, the respective documents must be in specific states:

*   **Plan**: `PROPOSED` → `APPROVED` (Required for major architectural changes)
*   **Story**: `DRAFT` → `OPEN` → `COMMITTED` (Required for code generation)
*   **Runbook**: `PROPOSED` → `ACCEPTED` (Required for implementation execution)

### 4. Directory Structure

*   `bin/`: The CLI executable.
*   `lib/`: The CLI library.
*   `agents.yaml`: Definitions of the "Governance Panel" roles.
*   `adrs/`: Architecture Decision Records (immutable design documents).
*   `workflows/`: Workflow files for Agent instructions.
*   `cache/`: Cache for agent plans, stories, and runbooks.
*   `templates/`: Template files for agent stories, runbooks, and plans.
*   `rules/`: Global rules for the agent.
*   `instructions/<agent>/`: Instructions for the agent.

## Usage Guide

For detailed instructions, see the "Available Commands" table below.

### Quick Start

**1. Create a Story**
```bash
./.agent/bin/agent new-story
```

**2. Generate a Plan (AI)**
```bash
./.agent/bin/agent plan STORY-ID
```

**3. Generate a Runbook (AI)**
```bash
./.agent/bin/agent new-runbook STORY-ID
```

**4. Implement Changes (AI)**
```bash
./.agent/bin/agent implement RUNBOOK-ID
```

**5. Preflight & Commit**
```bash
./.agent/bin/agent preflight --story STORY-ID
./.agent/bin/agent commit --story STORY-ID
```

### Available Commands (Reference)

| Command | Description | Usage / Arguments |
| :--- | :--- | :--- |
| **`preflight`** | Run governance preflight checks (Lint, Tests, AI). | `preflight [--story <ID>] [--ai] [--base <BRANCH>] [--provider <gh/gemini/openai>]` |
| **`commit`** | Commit changes with a governed message format. | `commit [--story <ID>] [--runbook <ID>]` |
| **`pr`** | Open a GitHub Pull Request (runs preflight first). | `pr [--story <ID>] [--web] [--draft]` |
| **`new-story`** | Interactive prompt to create a new Story. | `new-story [STORY_ID]` |
| **`new-adr`** | Create a new Architectural Decision Record (ADR). | `new-adr [TITLE]` |
| **`new-plan`** | Create a new implementation plan manually. | `new-plan [PLAN_ID]` |
| **`new-runbook`** | Generate an implementation runbook using AI Panel. | `new-runbook <STORY_ID>` |
| **`plan`** | Generate an implementation plan using AI. | `plan <STORY_ID>` |
| **`implement`** | Execute an implementation runbook using AI (Coder). | `implement <RUNBOOK_ID>` |
| **`match-story`** | Identify the best Story for a set of changed files. | `match-story --files "<file1> <file2>..."` |
| **`validate-story`** | Validate the schema of a story file. | `validate-story <STORY_ID>` |
| **`list-stories`** | List all stories in `.agent/cache/stories`. | `list-stories` |
| **`list-plans`** | List all plans in `.agent/cache/plans`. | `list-plans` |
| **`list-runbooks`** | List all runbooks in `.agent/cache/runbooks`. | `list-runbooks` |
| **`impact`** | Run impact analysis for a story (Stub). | `impact <STORY_ID>` |
| **`panel`** | Simulate a governance panel review (Stub). | `panel <STORY_ID>` |
| **`run-ui-tests`** | Run UI journey tests (Stub). | `run-ui-tests <STORY_ID>` |
| **`help`** | Show help message for the CLI. | `help [COMMAND]` |

### The Governance Panel
The `preflight` command convenes a panel of virtual agents defined in `.agent/agents.yaml`.
*   **Architect**: Checks for ADR compliance.
*   **QA**: Checks for Test Strategy.
*   **Security**: Scans for secrets and PII.
*   **Product**: Validates Acceptance Criteria.
*   **SRE**: Checks for OpenTelemetry instrumentation.
*   **Tech Writer**: Ensures matching documentation updates.

## Best Practices
*   **Monorepo Scoping**: Stories are now scoped (e.g., `WEB-xxx`, `MOBILE-xxx`). Use the correct prefix.
*   **Documentation**: If you change logic, you *must* update docs (README, ADRs), or the Tech Writer agent will complain.
*   **Compliance**: If your Story description mentions "GDPR" or "PII", the Security agent will strictly enforce checklist review.

## AI-Powered Capabilities


the Agent CLI now features native Python-based AI integration, supporting robust governance workflows.

> [!NOTE]
> **Data Privacy**: For details on how data is handled by external AI providers, please refer to [ADR 016](.agent/adrs/ADR-016-openai-data-processor.md).
> All context (Stories, Plans, Code Diffs) is **automatically scrubbed** of PII and Secrets (Emails, IPs, API Keys) before transmission.


### Supported Providers
1.  **Google Gemini** (Recommended): `GEMINI_API_KEY` (or `GOOGLE_GEMINI_API_KEY`). Uses `gemini-1.5-pro` with large context window.
2.  **OpenAI**: `OPENAI_API_KEY`. Uses `gpt-4o` with large context window.
3.  **GitHub CLI**: Fallback if no keys present. Uses `gh models run`. Note: Restricted context (8k tokens) requires aggressive chunking.

### AI Commands

**1. Generate Implementation Plan**
Analyze a Story and generate a step-by-step technical plan.
```bash
./.agent/bin/agent plan STORY-ID
```

**2. Generate Runbook**
Create a detailed, executable runbook from a Story or Plan, reviewed by the Governance Panel.
```bash
./.agent/bin/agent new-runbook STORY-ID
```

**3. Implement Code**
Execute a Runbook step-by-step, generating code edits and verifying compliance.
```bash
./.agent/bin/agent implement RUNBOOK-ID
```

**4. Match Story**
Identify the best existing Story for a set of changed files (useful for `commit` workflow).
```bash
./.agent/bin/agent match-story --files "src/foo.py src/bar.py"
```

### AI-Powered Governance (Preflight)

The `preflight --ai` command convenes a **Full Governance Council** of 9 specialized agents (Architect, Security, Compliance, QA, Docs, Observability, Backyard, Mobile, Web) to review your changes.

**Key Features:**
*   **Full Council**: 9 distinct roles with specialized prompts.
*   **Smart Chunking**: Large diffs are automatically split into chunks (default 6000 chars) to ensure 100% code coverage.
*   **Resilience**: Automatic retries for rate limits and context window management.
*   **Reporting**: Full detailed reports are saved to `.agent/logs/`.

```bash
# Run AI Governance Council on staged changes
./.agent/bin/agent preflight --story STORY-ID --ai

# Run against a base branch
./.agent/bin/agent preflight --story STORY-ID --ai --base main
```
## Development & Testing

To run the agent's test suite locally:

1.  **Install Test Dependencies**:
    ```bash
    pip install pytest pytest-mock typer rich
    ```

2.  **Run All Tests**:
    ```bash
    PYTHONPATH=.agent/src pytest .agent/tests/
    ```

3.  **Run Specific Suites**:
    ```bash
    # Core logic tests
    PYTHONPATH=.agent/src pytest .agent/tests/core/
    
    # Command integration tests
    PYTHONPATH=.agent/src pytest .agent/tests/commands/
    ```
