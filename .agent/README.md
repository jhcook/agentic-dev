# Agentic Development Tool

The **Agentic Development Tool** (`agent`) is an AI-powered CLI that automates, governs, and enhances the software development lifecycle. It enforces Story-Driven Development, ensuring all code changes are traceable to approved requirements and comply with architectural and security standards.

## Architecture

```text
agent/
├── commands/     # CLI layer — Typer commands, argument parsing, Rich output
├── core/         # Business logic — AI service, config, auth, governance
│   ├── ai/       # Multi-provider AI service (Gemini, Vertex AI, OpenAI, Anthropic, GH)
│   └── auth/     # Credential validation and secret management
├── sync/         # Notion bidirectional sync
├── db/           # Journey index and local state
└── infra/        # File system, git integration, external tools
```

### Key Components

- **Multi-Provider AI Service** — Supports Gemini, Vertex AI, OpenAI, Anthropic, and GitHub Copilot with automatic fallback on rate limits.
- **Smart AI Router** — Selects model based on task complexity and cost.
- **Governance Engine** — Multi-role preflight checks (Security, Architect, QA, Compliance, Observability).
- **ADK Multi-Agent Panel** — Optional Google ADK-powered parallel governance ([ADR-029](adrs/ADR-029-adk-multi-agent-integration.md)).
- **User Journeys** — Behavioural contracts as YAML with test coverage tracking ([ADR-024](adrs/ADR-024-introduce-user-journeys.md)).
- **Interactive Repair** — AI-driven auto-fix for governance failures ([ADR-015](adrs/ADR-015-interactive-preflight-repair.md)).
- **Voice Integration** — Hands-free development via voice commands ([ADR-007](adrs/ADR-007-voice-service-abstraction-layer.md)).

## Installation

Prerequisites: Python 3.10+, Git.

```bash
pip install -e .agent/
```

## Configuration

Configuration lives in `.agent/etc/agent.yaml`. AI provider is set via the `provider` field:

```yaml
agent:
  # provider: gemini | vertex | openai | anthropic | gh
  provider: gemini
```

Credentials are provided via environment variables or the built-in secret store:

| Provider | Environment Variable |
|----------|---------------------|
| Gemini | `GEMINI_API_KEY` |
| Vertex AI | `GOOGLE_CLOUD_PROJECT` |
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| GitHub | `GITHUB_TOKEN` |

```bash
# Option A: Environment variable
export GEMINI_API_KEY="AIza..."

# Option B: Secret store
agent onboard
```

See [Getting Started](../docs/getting_started.md) for provider comparison and Vertex AI setup.
Secrets are managed via the system keyring ([ADR-006](adrs/ADR-006-encrypted-secret-management.md)).

## Commands

### Story-Driven Workflow

| Command | Description |
|---------|-------------|
| `agent new-story <ID>` | Create a new user story |
| `agent new-runbook <ID>` | Generate an implementation runbook |
| `agent new-plan <ID>` | Create a new implementation plan |
| `agent new-adr <ID>` | Create a new ADR |
| `agent implement <ID>` | Implement from a runbook |
| `agent preflight --story <ID> --ai` | Run governance checks |
| `agent commit -m "<message>"` | Commit with story tracking |
| `agent pr` | Create a pull request |

### Governance & Review

| Command | Description |
|---------|-------------|
| `agent panel <ID>` | Convene the AI governance panel |
| `agent impact <ID> --ai` | Run impact analysis |
| `agent audit` | Generate audit report |
| `agent lint` | Run linters (ruff, shellcheck, eslint) |
| `agent validate-story <ID>` | Validate story schema |
| `agent match-story` | Match staged files to a story |

### AI & Query

| Command | Description |
|---------|-------------|
| `agent query "<question>"` | Ask AI about the codebase |
| `agent list-models` | List available AI models |

### Journeys & Testing

| Command | Description |
|---------|-------------|
| `agent new-journey <ID>` | Create a user journey |
| `agent validate-journey <path>` | Validate journey YAML |
| `agent journey coverage` | Report journey → test coverage |
| `agent journey backfill-tests` | Generate test stubs for COMMITTED journeys |
| `agent run-ui-tests` | Run UI test suite |

### Listing & Discovery

| Command | Description |
|---------|-------------|
| `agent list-stories` | List all stories |
| `agent list-plans` | List all plans |
| `agent list-runbooks` | List all runbooks |
| `agent list-journeys` | List all journeys |

### Infrastructure

| Command | Description |
|---------|-------------|
| `agent sync push/pull/status/scan/janitor/init/flush` | Distributed sync with Notion |
| `agent config` | Manage configuration |
| `agent secret` | Manage encrypted secrets |
| `agent admin` | Launch management console |
| `agent mcp` | Manage MCP servers |
| `agent import` | Import artifacts from external sources |
| `agent onboard` | Interactive onboarding wizard |

## Governance & Compliance

The tool enforces **SOC2** and **GDPR** compliance by:

- Scrubbing PII from all AI prompts
- Linking all code changes to a Story
- Maintaining a comprehensive audit trail

For architectural decisions, see the [ADR Directory](adrs/).
