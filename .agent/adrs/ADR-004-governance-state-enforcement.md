# ADR-004: Governance State Enforcement Architecture

## Status
Accepted

## Context
In an agentic development environment where both human developers and AI agents contribute code, maintaining architectural integrity and strictly adhering to requirements is challenging. Traditional "loose" agile processes (Jira tickets + loose code) often lead to:
1. **Scope Creep**: AI agents might hallucinate features not in the requirements.
2. **Missing Safety Checks**: Security or compliance requirements defined in stories are ignored during implementation.
3. **Architectural Drift**: Code is written without a pre-approved implementation plan, violating system design patterns.

We need a mechanism to enforce that *no code is written* until the requirements (Story) and the implementation plan (Runbook) are explicitly approved.

## Decision
We will enforce a **Strict State Machine** for the development lifecycle, implemented via the `agent` CLI.

### 1. The State Hierarchy
The system recognizes three distinct artifact types with dependent states:
1. **Plan** (High-level Epic/Architecture)
   - Must be `APPROVED` before Stories can be created.
2. **Story** (User Requirements)
   - Must be `COMMITTED` (locked) before Runbooks can be created.
   - Contains: Problem Statement, User Story, Acceptance Criteria, Test Strategy.
3. **Runbook** (Implementation Plan)
   - Must be `ACCEPTED` before the `agent implement` command works.
   - Contains: Exact changes to be made, file paths, and rollback steps.

### 2. CLI Enforcement
The `agent` CLI acts as the gatekeeper. It is not just a helper tool but a *compliance engine*:
- `agent new-story <PlanID>`: Fails if Plan is not `APPROVED`.
- `agent new-runbook <StoryID>`: Fails if Story is not `COMMITTED`.
- `agent implement <StoryID>`: Fails if Runbook is not `ACCEPTED`.

### 3. State Storage
States are stored in the frontmatter of the markdown artifacts (e.g., `Status: APPROVED`) and indexed in the local SQLite database (`agent.db`) for fast lookups by the CLI.

## Consequences

### Positive
1. **Determinism**: AI agents cannot "start coding" without a clear, approved plan.
2. **Compliance**: Regulatory checks (e.g., impact analysis, security reviews) are forced into the Story/Runbook phase before code exists.
3. **Context Window Efficiency**: When the `implant` command runs, it only needs the `Runbook`, not the entire history of the project, as the Runbook contains the pre-digested instructions.

### Negative
1. **Friction**: Developers cannot just "open a file and hack". They must create a Story and Runbook first.
2. **Overhead**: For trivial one-line fixes, the Plan -> Story -> Runbook process is heavyweight. (Mitigation: We may introduce a `hotfix` flow later, but it is currently out of scope).
