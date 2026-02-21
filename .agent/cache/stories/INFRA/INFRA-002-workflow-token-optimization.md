# INFRA-002: Workflow Token Optimization

## State
INFRA-002-002-002-002-002-002

## Problem Statement
The current Agent workflows (`workflows/*.md`) are detailed manual instruction manuals. This causes the Agent to burn "reasoning tokens" simulating logic that already exists (or should exist) in the Python CLI (`agent` commands). This leads to:
1.  **High Cost**: Paying for tokens to simulate deterministic logic.
2.  **Divergence**: Markdown instructions getting out of sync with Python code.
3.  **Inefficiency**: Slow execution of manual steps.

Additionally, configuration files (`router.yaml`, `agents.yaml`) are scattered in the root, and the Runbook structure is hardcoded in Python, making customization difficult.

## User Story
As an **Agentic Developer**,
I want **workflows to act as thin wrappers around Python CLI commands**,
So that I can **execute complex logic efficiently, cheaply, and consistently** while maintaining a single source of truth in the Python codebase.

## Acceptance Criteria
- [ ] **Workflow Parity**:
    - `workflows/pr.md` executes `env -u VIRTUAL_ENV uv run agent pr --draft --web`
    - `workflows/commit.md` executes `env -u VIRTUAL_ENV uv run agent commit --ai`
    - `workflows/preflight.md` executes `env -u VIRTUAL_ENV uv run agent preflight --ai --base main`
    - `workflows/runbook.md` executes `env -u VIRTUAL_ENV uv run agent new-runbook`
    - `workflows/implement.md` executes `env -u VIRTUAL_ENV uv run agent implement` (immediately)
- [ ] **Config Relocation**:
    - `.agent/agents.yaml` moved to `.agent/etc/agents.yaml`
    - `.agent/router.yaml` moved to `.agent/etc/router.yaml`
    - `config.py` updated to load from `etc/`
- [ ] **Templates**:
    - Runbook structure extracted to `.agent/templates/runbook-template.md`
    - `runbook.py` updated to use the template

## Non-Functional Requirements
- **Zero-Shot Execution**: The Agent should see the workflow file and immediately know to run the command without further "thinking".
- **Backward Compatibility**: Existing commands should still function after config move.

## Impact Analysis Summary
- **Components touched**: `.agent/workflows/`, `.agent/src/agent/commands/`, `.agent/etc/`, `.agent/templates/`.
- **Risks**: Temporary breakage of CLI if paths are not updated correctly in `config.py`.

## Test Strategy
- Manual verification of each workflow command.
- Verification that `env -u VIRTUAL_ENV uv run agent new-runbook` produces the expected output using the new template.

## Implementation Plan

### Phase 5: Agent-Driven Intelligence (CLI Cleanup)
Remove external AI calls from CLI commands. The Agent (Antigravity) will generate content.

#### [MODIFY] [runbook.md](file:///Users/jcook/repo/agentic-dev/.agent/workflows/runbook.md)
- Update wrapper constraints.
- Step 1: `Run: agent new-runbook <ID>` (Creates scaffold).
- Step 2: "Populate the runbook file. **REFER TO** the following sources for requirements (Do not hallucinate rules):"
    - `Context: .agent/rules/`
    - `Context: .agent/etc/agents.yaml`
    - `Context: .agent/instructions/`
- This ensures the workflow points to the Single Source of Truth without duplicating text.

#### [MODIFY] [commit.py] (in `workflow.py`)
- Update `commit` command to accept optional `--message` / `-m` argument.
- If `-m` is provided, skip interactive prompt.

#### [MODIFY] [commit.md](file:///Users/jcook/repo/agentic-dev/.agent/workflows/commit.md)
- Step 1: "Generate a Conventional Commit message based on staged changes."
- Step 2: `Run: agent commit -m "<MESSAGE>"` (Remove `--ai` default).
