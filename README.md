# Agent

An AI-powered governance and workflow CLI for software development teams. Agent automates story creation, implementation planning, code review, and compliance enforcement — all from the command line.

## Introduction

Read our core philosophy on how `agentic-dev` approaches AI-assisted engineering:
- [Engineering Discipline in the Age of AI: The End of "Vibe Coding"](docs/engineering-discipline.md)
- [Commanding the AI Assembly Line: Configuration, Ingestion, and Visualization](docs/config-and-visualization.md)
- [Credential Security in the Agentic Workflow: Safety Meets Absolute Convenience](docs/credential-security.md)
- [Eradicating Developer Toil: The Magic of the Agentic CLI](docs/developer-experience.md)

## What It Does

- **Story & Runbook Management** — Create, track, and implement user stories with structured workflows and state transitions.
- **AI Governance Panel** — Multi-role preflight checks (Security, Architect, QA, Compliance, Observability) that validate your changes before commit.
- **Parallel ADK Engine** — Blazing fast governance evaluation leveraging the Google Agent Development Kit for concurrent multi-agent analysis.
- **Oracle Preflight Pattern** — Advanced context retrieval fusing Notion, NotebookLM via MCP, and an embedded zero-server Vector database for high fidelity AI decisions.
- **Multi-Provider AI** — Works with Gemini, Vertex AI, OpenAI, Anthropic, and GitHub Copilot. Automatic fallback between providers on rate limits.
- **Smart Test Selection** — Performs real-time Python impact analysis to intelligently group and selectively execute necessary tests.
- **User Journey Testing** — Define user journeys as YAML, auto-generate test stubs, enforce implementation gates, and track test coverage.
- **Voice UX Reviews** — Analyze hands-free voice sessions (`agent review-voice`) to grade agent latency, accuracy, tone, and interruption handling.
- **Automated License Headers** — Enforces and automatically generates required copyright headers across specific file types in the project.

## Quick Start

See [Getting Started](docs/getting_started.md) for full instructions on prerequisites, how to get `.agent` into your repository, configuration, and running `agent onboard`.

### Run

The standard Agentic Development workflow follows a strict requirements-to-code pipeline:

```bash
# 1. Create a tracking story
agent new-story INFRA-001

# 2. Automatically generate an implementation plan (Runbook)
agent new-runbook INFRA-001

# 3. Have the AI implement the approved Runbook
agent implement INFRA-001

# 4. Run the Parallel Governance Council checks
# (Architect, Security, QA, Compliance, etc.)
agent preflight --story INFRA-001

# 5. Commit with story tracking and automated message
agent commit
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
| `agent review-voice` | Analyze a completed voice session and generate UX feedback |
| `agent audit` | Generate audit report |
| `agent lint` | Run linters (ruff, shellcheck, eslint) |
| `agent validate-story` | Validate story schema |
| `agent validate-journey` | Validate journey YAML |
| `agent match-story` | Match staged files to a story |
| `agent run-ui-tests` | Run UI test suite |

### Voice UX Reviews

The `agent review-voice` command enables you to evaluate the quality of a voice agent session. It analyzes latency, accuracy, tone, and interruption handling to provide structured UX feedback on the voice bot's performance.

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

- [Onboarding Guide](docs/getting_started.md) — How to install and configure `.agent` in your repository
- [Provider Setup](.agent/docs/getting_started.md) — AI provider comparison, credentials, and advanced configuration
- [Release Guide](docs/release-guide.md) — Packaging and release process
- [Configuration & Visualization](docs/config-and-visualization.md) — Managing the AI assembly line
- [Credential Security](docs/credential-security.md) — AES-256 and native OS keyring integration
- [Developer Experience](docs/developer-experience.md) — Frictionless operations via `match-story`, `commit`, and `pr`
- [ADRs](.agent/adrs/) — Architectural decision records
- [Workflows](.agent/workflows/) — Detailed workflow instructions

## License

Apache License 2.0
