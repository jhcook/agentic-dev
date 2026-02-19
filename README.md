# Agent

An AI-powered governance and workflow CLI for software development teams. Agent automates story creation, implementation planning, code review, and compliance enforcement — all from the command line.

## What It Does

- **Story & Runbook Management** — Create, track, and implement user stories with structured workflows and state transitions.
- **AI Governance Panel** — Multi-role preflight checks (Security, Architect, QA, Compliance, Observability) that validate your changes before commit.
- **Multi-Provider AI** — Works with Gemini, Vertex AI, OpenAI, Anthropic, and GitHub Copilot. Automatic fallback between providers on rate limits.
- **Notion Sync** — Bidirectional synchronization of stories, plans, and ADRs with Notion.
- **User Journey Testing** — Define user journeys as YAML, generate test stubs, and track coverage.

## Quick Start

### Prerequisites

- Python 3.10+
- Git

### Install

```bash
pip install -e .agent/
```

### Configure

Set your AI provider credentials:

```bash
# Option A: Environment variable
export GEMINI_API_KEY="AIza..."

# Option B: Built-in secret store
agent onboard
```

See [Getting Started](docs/getting_started.md) for provider comparison and Vertex AI setup.

### Run

```bash
# Create a story
agent new-story INFRA-001

# Run governance checks
agent preflight --story INFRA-001 --ai

# Commit with governance
agent commit -m "feat(api): add caching layer"
```

## Core Workflows

| Command | Description |
|---------|-------------|
| `agent new-story` | Create a new user story |
| `agent new-runbook` | Generate an implementation runbook |
| `agent new-plan` | Create a new implementation plan |
| `agent new-journey` | Create a new user journey |
| `agent new-adr` | Create a new ADR |
| `agent implement` | Implement from a runbook |
| `agent preflight` | Run governance checks |
| `agent commit` | Commit with story tracking |
| `agent pr` | Create a pull request |

## Governance & Review

| Command | Description |
|---------|-------------|
| `agent panel` | Convene the AI governance panel |
| `agent impact` | Run impact analysis |
| `agent audit` | Generate audit report |
| `agent lint` | Run linters (ruff, shellcheck, eslint) |
| `agent validate-story` | Validate story schema |
| `agent validate-journey` | Validate journey YAML |
| `agent match-story` | Match staged files to a story |
| `agent run-ui-tests` | Run UI test suite |

## AI & Query

| Command | Description |
|---------|-------------|
| `agent query` | Ask AI about the codebase |
| `agent list-models` | List available AI models |

## Listing & Discovery

| Command | Description |
|---------|-------------|
| `agent list-stories` | List all stories |
| `agent list-plans` | List all plans |
| `agent list-runbooks` | List all runbooks |
| `agent list-journeys` | List all journeys |

## Sub-Apps

| Command | Description |
|---------|-------------|
| `agent sync` | Distributed sync (push/pull/status/scan/janitor/init/flush) |
| `agent journey` | Journey management (coverage, backfill-tests) |
| `agent config` | Manage configuration |
| `agent secret` | Manage encrypted secrets |
| `agent admin` | Launch management console |
| `agent mcp` | Manage MCP servers |
| `agent import` | Import artifacts from external sources |
| `agent onboard` | Interactive onboarding wizard |

## Documentation

- [Getting Started](docs/getting_started.md) — Provider setup, credentials, and configuration
- [Release Guide](docs/release-guide.md) — Packaging and release process
- [ADRs](.agent/adrs/) — Architectural decision records
- [Workflows](.agent/workflows/) — Detailed workflow instructions

## License

Apache License 2.0
