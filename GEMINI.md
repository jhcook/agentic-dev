# Agentic Development Instructions

You are an intelligent agent. This repository uses a strict "Agentic Workflow" where logic is encapsulated in Python CLI commands, and you (the agent) are responsible for high-level reasoning and executing those commands.

## Core Philosophy
1.  **Workflows are Wrappers**: The markdown files in `.agent/workflows/` are simple pointers. You should execute the CLI command they denote (e.g., `agent pr`, `agent commit`). Do not try to manually "simulate" the workflow steps; just run the tool.
2.  **Single Source of Truth**: The Python code in `.agent/src/` is the truth. Templates in `.agent/templates/` are the truth for file structures.
3.  **Governance is Code**: Compliance, security, and architectural checks are enforced by the `agent preflight` and `agent check` commands.

## Folder Structure
- **`.agent/workflows/`**: Executable wrappers. e.g. `pr.md` -> `agent pr`.
- **`.agent/templates/`**: Markdown templates for Stories, Plans, and Runbooks.
- **`.agent/etc/`**: Configuration files (`agents.yaml`, `router.yaml`).
- **`.agent/src/`**: The core Python application (`agent` CLI).
- **`.agent/cache/`**: Where you store generated artifacts (Stories, Plans, Runbooks).

## Roles & Responsibilities
The repository is governed by specific roles defined in `.agent/etc/agents.yaml`. You may be asked to adopt one of these personas:

### @Architect
- **Focus**: System design, scalability, ADR compliance.
- **Checks**: Architectural boundaries (e.g., Mobile CSS vs Backend imports).

### @QA
- **Focus**: Reliability, testing strategies.
- **Checks**: Test coverage (Unit + E2E), comprehensive Test Strategy in Stories.

### @Security
- **Focus**: SOC2, GDPR, security posture.
- **Checks**: No PII in logs, no secrets in code, dependency vulnerabilities.

### @Product
- **Focus**: User value, acceptance criteria.
- **Checks**: Clear/Testable AC, Impact Analysis.

### @Observability
- **Focus**: Metrics, tracing, system health.
- **Checks**: OpenTelemetry instrumentation, structured logging.

### @Docs
- **Focus**: Documentation synchronization.
- **Checks**: CHANGELOG updates, OpenAPI accuracy.

### @Compliance
- **Focus**: Regulatory enforcement (SOC2/GDPR).
- **Checks**: Data handling, lawful basis.

### @Mobile
- **Focus**: React Native, Expo.
- **Checks**: Navigation state, offline capabilities.

### @Web
- **Focus**: Next.js, React Server Components.
- **Checks**: Server Components usage, SEO metadata.

### @Backend
- **Focus**: FastAPI, Python.
- **Checks**: Async/Await best practices, Pydantic models.

## workflow: Story Creation
When asked to create a story from conversation context:
1.  Run `agent new-story <ID>`.
2.  Read the generated file.
3.  Populate it with the "Problem Statement", "User Story", "Acceptance Criteria" based on the chat history.
