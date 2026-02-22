# Architecture Overview

This document provides a high-level overview of the Agentic Development Framework's architecture. The framework is built around a command-line interface (CLI) that orchestrates AI-driven agents to automate the software development lifecycle, enforce governance, and interact with external systems.

## Core Architecture

The system is composed of the following key layers:

1. **CLI Layer (`agent/commands/`)**: The user-facing interface built with `Typer`. Maps user commands to internal workflows (e.g., `agent implement`, `agent preflight`, `agent onboard`).
2. **Core Modules (`agent/core/`)**: The foundational building blocks that power the CLI.
3. **Subsystems & Integrations**: External services and protocols (e.g., Supabase, Notion, MCP, Voice UI) that extend the agent's capabilities.
4. **Data Cache (`.agent/cache/`)**: The local filesystem storage for stories, runbooks, and journeys, acting as the Single Source of Truth locally.

---

## The CLI Layer

The CLI is the primary entry point for developers. It is broken down into sub-applications and commands located in `src/agent/commands/`:

- **Workflow Commands** (`implement.py`, `journey.py`, `story.py`, `runbook.py`): Drive the SDLC forward.
- **Governance Commands** (`audit.py`, `check.py`, `lint.py`): Enforce repo health through AST parsing and AI-driven static analysis (e.g., the AI Governance Panel).
- **Sub-Apps** (`admin.py`, `config.py`, `mcp.py`, `secret.py`): Manage configurations, background processes, and external integrations.

---

## Core Modules (`src/agent/core/`)

The CLI delegates business logic to specialized modules within `agent/core/`:

### 1. AI Orchestration (`agent/core/ai/` & `agent/core/engine/`)

The AI engine is responsible for interacting with Large Language Models (LLMs). It abstracts the underlying provider (Gemini, Vertex AI, OpenAI, Anthropic, or GitHub) and handles prompt generation, tool calling, and structured data parsing.

- **Provider Abstraction**: Allows swapping LLMs dynamically via the `--provider` flag.
- **ADK Engine**: The Agent Development Kit (ADK) powers multi-agent panel simulations (e.g., `@Architect`, `@Security`), allowing specialized personas to debate and review code.

### 2. Context Building (`agent/core/context.py` & `agent/core/context_builder.py`)

AI models require context to make sound decisions. The context builder aggregates information from:

- **Filesystem**: Reads local files and filters via `.gitignore`.
- **Git State**: Analyzes staged vs. unstaged changes.
- **Dependency Graph**: Performs static code analysis using AST to identify "blast radius" during impact analysis.

### 3. Governance and Security (`agent/core/governance.py` & `agent/core/security.py`)

Enforces the strict quality and compliance gates of the framework.

- Validates that stories have Acceptance Criteria, Test Strategies, and Rollback Plans.
- Enforces the **Journey Gate**, ensuring that no implementation begins until a valid `JRN-XXX` behavioral contract is present.
- **Secret Management**: Uses AES-256-GCM encryption to safely store API keys locally (`.agent/secrets/`) without exposing them to plain text configuration files.

### 4. Integration Modules (`agent/core/notion/` & `agent/core/mcp/`)

- **Notion Sync**: Bi-directional synchronization between the local `.agent/cache/` (Markdown/YAML files) and an external Notion workspace to maintain absolute alignment between project management and source code.
- **MCP (Model Context Protocol)**: Connects the agent to external tool-calling backends (like Google NotebookLM). It allows the local CLI to retrieve deep context that doesn't fit in the local cache or access tools outside its immediate execution environment.

---

## Subsystems

### The Agent Management Console (`agent admin`)

A local offline-first web platform utilizing FastAPI (backend) and React/Vite (frontend). It provides a graphical dashboard and Kanban views to interact with the project cache when the CLI is less optimal.

### Voice Interaction (`agent/core/voice.py`)

A unique subsystem enabling hands-free governance and AI-assisted pair programming.

- Uses `deepgram-sdk` or local inference (`onnxruntime`).
- Supports an interactive `review-voice` loop, where the system analyzes voice session logs for user experience metrics (latency, human interruptions, tone) and feeds them into the AI Panel for actionable feedback.

---

## Data Flow: The Agentic SDLC

1. **Design**: User runs `agent new-story`. A Markdown file is generated in `.agent/cache/stories/`.
2. **Sync**: `agent sync` watches for changes and pushes the Draft story to Notion.
3. **Planning**: `agent new-runbook` constructs an implementation plan for a committed story.
4. **Implementation**: `agent implement` leverages the Journey Gate, reads the Runbook, and iteratively edits the code while continuously running `make test` or `pytest`.
5. **Preflight**: Before committing, `agent preflight` invokes the ADK multi-agent panel to perform final governance and security checks, optionally interacting with the user via voice mode to resolve blockers.
6. **Commit**: `agent commit` constructs a conventional commit message referencing the governed story.
