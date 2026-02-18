# Agentic Development Tool

The **Agentic Development Tool** (`agent`) is an AI-powered CLI designed to automate, govern, and enhance the software development lifecycle. It enforces a strict "Story-Driven Development" workflow, ensuring that all code changes are traceable to approved requirements and comply with architectural and security standards.

## Architecture Overview

The tool follows a layered architecture:

- **CLI Layer** (`agent/commands/`): Handles user interaction, argument parsing (via Typer), and output formatting (via Rich).
- **Core Layer** (`agent/core/`): Contains the business logic, AI service integration, and governance rules. This layer is decoupled from the CLI to support reusability.
- **Infrastructure Layer** (`agent/infra/`): Manages file system operations, git integration, and external tool execution.

### Key Components

- **Smart AI Router**: Dynamically selects the best AI model (Gemini, OpenAI, Anthropic) based on task complexity and cost.
- **Governance Engine**: Enforces preflight checks, ensuring stories are well-defined and code changes are safe.
- **ADK Multi-Agent Panel**: Optional Google ADK-powered governance panel with parallel agent execution (see [ADR-029](adrs/ADR-029-adk-multi-agent-integration.md)).
- **User Journeys**: Behavioral contracts that define what the system does from a user's perspective (see [ADR-024](adrs/ADR-024-introduce-user-journeys.md)).
- **Interactive Repair**: Automatically detects and fixes governance failures using AI (see [ADR-015](adrs/ADR-015-interactive-preflight-repair.md)).
- **Voice Integration**: Supports hands-free development via real-time voice commands (see [ADR-007](adrs/ADR-007-voice-service-abstraction-layer.md)).

## Installation

Prerequisites: Python 3.11+, Node.js (for web/mobile checks), Git.

1. **Clone the repository**:

   ```bash
   git clone <repo_url>
   cd <repo_dir>
   ```

2. **Set up the environment**:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Install the CLI**:

   ```bash
   pip install -e .
   ```

## Configuration

Configuration is managed via `.agent/config.yaml` (implementation pending) and environment variables.

- `AGENT_AI_PROVIDER`: Default AI provider (`gemini`, `openai`, `anthropic`).
- `AGENT_API_KEY`: API key for the selected provider.

Secrets are managed securely via the system keyring (see [ADR-006](adrs/ADR-006-encrypted-secret-management.md)).

## Usage

### Core Workflows

- **Create a Journey**: `agent new-journey JRN-001`
- **Create a Story**: `agent new-story`
- **Generate Runbook**: `agent new-runbook WEB-001`
- **Implement**: `agent implement WEB-001`
- **Preflight Checks**: `agent preflight --story WEB-001 --ai`
- **Governance Panel**: `agent panel WEB-001`
- **Impact Analysis**: `agent impact WEB-001 --ai`
- **Commit**: `agent commit --story WEB-001 --ai`
- **Pull Request**: `agent pr --story WEB-001`
- **Audit**: `agent audit --output report.json`

  Use `--interactive` on preflight to auto-fix violations. Use `--panel-engine adk` for multi-agent governance. Use `--thorough` for deeper AI review with full-file context and false-positive filtering (uses more tokens).

### Voice Mode

Start the voice agent for hands-free assistance:

```bash
agent voice start
```

## Governance & Compliance

This tool enforces **SOC2** and **GDPR** compliance by:

- Scrubbing PII from all AI prompts.
- ensuring all code changes are linked to a Story.
- Maintaining a comprehensive audit trail.

For more details on architectural decisions, see the [ADR Directory](adrs/).
