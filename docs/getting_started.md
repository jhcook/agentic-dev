# Getting Started with Agentic Development

The Agent CLI is designed to be installed locally within your project repository to provide AI-powered governance and workflow automation.

## Prerequisites

- **Python 3.10+** and **pip**
- **Git** (for repository management)

## Installation

1. Copy the `.agent` directory into the root of your repository.
2. Create a virtual environment and install the CLI:

```bash
cd /path/to/your/repo

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the agent CLI
pip install -e .agent/
```

## Credentials

The Agent requires access to an AI provider to function. The default provider is Gemini. Configure this via an environment variable initially:

```bash
export GEMINI_API_KEY="your-api-key-here"
```

## Bootstrapping the Repository

To initialize the Agent configuration, templates, and directory structures in your repository, run the onboard command:

```bash
agent onboard
```

This interactive wizard will guide you through:

1. Setting up your core `.agent/etc/agent.yaml` configuration.
2. Selecting your preferred AI provider (Gemini, Vertex, OpenAI, Anthropic, or GitHub CLI).
3. Establishing the `.agent/cache` structure for tracking stories, runbooks, and journeys.
4. Saving your credentials into the securely encrypted secret store.
5. Configuring the NotebookLM MCP server for advanced context retrieval.

For detailed provider authentication (such as Vertex AI setup) and advanced configuration, see the comprehensive [Agent Documentation](.agent/docs/getting_started.md).
