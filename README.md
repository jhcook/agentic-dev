# The Agent

The Agent is an intelligent, colocated developer assistant designed to automate software development tasks, enforce governance, and facilitate high-level reasoning within your repository. It encapsulates logic in Python CLI commands to generate architectural decision records (ADRs), plans, stories, and runbooks.

## Core Philosophy

- **Colocated**: The agent lives inside your repository in the `.agent` directory.
- **Workflow-Driven**: Automates defined workflows (e.g., Pull Requests, Impact Analysis).
- **Governance-First**: Enforces strict state transitions (Plan → Story → Runbook) and compliance checks.
- **Agentic**: Designed to work with AI agents that can read the code and execute the CLI commands.

## Features

- **Workflow Automation**: Run predefined workflows (`agent pr`, `agent commit`).
- **Govornance & Compliance**: Built-in `preflight` checks and architectural oversight.
- **AI Integration**: Query codebase, list models, and generate artifacts using LLMs.
- **Artifact Management**: Manages Plans, Stories, and Runbooks in `.agent/cache`.

## Onboarding

To use the Agent in your repository:

### 1. Get the Latest Release
Download the `agent-release.tar.gz` from the latest release of the `agentic-dev` repository.

### 2. Install
Extract the release into the root of your repository:
```bash
tar -xzf agent-release.tar.gz
```
This will create a `.agent` directory.

### 3. Setup Dependencies
Install the required Python dependencies:
```bash
pip install -e .agent
```

### 4. Initialize
Run the onboarding command to set up your environment, check dependencies (including `gh`), and configure API keys for OpenAI, Gemini, and Anthropic:
```bash
./.agent/bin/agent onboard
```

### 5. Usage
You can now run the agent commands using the binary wrapper:
```bash
./.agent/bin/agent --help
```
*Tip: You may want to alias this command in your shell profile: `alias agent="./.agent/bin/agent"`*