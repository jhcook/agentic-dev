# INFRA-015: Implement Agent Onboard

## State
COMMITTED

## Problem Statement
New developers or existing developers setting up fresh environments currently face a manual, error-prone process to get the `agent` CLI working. They must manually install system dependencies such as Python and Git, configure sensitive environment variables (API keys) in `.env`, and potentially initialize the `.agent` specific directory structure. This friction reduces adoption and increases the "time to first commit".

## User Story
As a new developer, I want to run a single command `env -u VIRTUAL_ENV uv run agent onboard` that checks my system dependencies, interactively sets up my configuration, and initializes the agent workspace so that I can start working immediately without consulting fragmented documentation.

## Acceptance Criteria
- [ ] **Dependency Check**: Checks for required binaries (Python 3, Git). Checks for *recommended* binaries (Docker, GitHub CLI `gh`) and warns if missing.
- [ ] **Interactive Config**: Prompts for missing `.env` variables (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) using masked input.
- [ ] **Provider Selection**: Prompts user to select a default AI provider and saves it to `agent.yaml`.
- [ ] **Model Selection**: Uses `env -u VIRTUAL_ENV uv run agent list-models` to let the user choose a default model for the selected provider.
- [ ] **Idempotency**: If `.env` exists, only prompts for specific keys that are missing. Does not overwrite existing valid configuration.
- [ ] **Environment Init**: Ensures `.agent/` directory and children exist. Handles edge cases gracefully.
- [ ] **Security Check**: Verifies that `.gitignore` exists and includes `.env`.
- [ ] **Verification**: Runs a "Hello World" AI completion to verify credentials and connectivity.
- [ ] **Frontend Setup**: Checks for `node` and `npm`, and runs `npm install` in `.agent/src/web` if present.
- [ ] **Tour**: Displays a guided tour of core commands (`env -u VIRTUAL_ENV uv run agent story`, `env -u VIRTUAL_ENV uv run agent preflight`, `env -u VIRTUAL_ENV uv run agent pr`) upon completion.

## Non-Functional Requirements
- **Security**: API keys must be masked during input and stored in `.env` with restricted permissions (e.g., `chmod 600`).
- **Usability**: Clear prompts. Defaults offered where possible.
- **Resilience**: Use `pathlib` for robust file handling. Handle permissions errors gracefully.
- **Portability**: targeted for macOS/Linux environment. Windows usage should warn or fail fast if unsupported.

## Linked ADRs
- N/A

## Impact Analysis Summary
Components touched: `agent/commands/onboard.py`, `agent/core/utils.py`, `README.md`, `CONTRIBUTING.md`.
Workflows affected: Developer Onboarding.
Risks identified: Overwriting config (mitigated by idempotency).

## Test Strategy
- **Unit Tests**:
    - Mock `shutil.which` for dependency checks.
    - Mock `typer.prompt` (or `input`) to simulate user interaction.
    - Verify `write_env` logic correctly appends/updates without destroying data.
- **Negative Tests**:
    - Simulate `.agent` blocking file scenario.
    - Simulate permission denied on writing `.env`.
- **Manual Verification**: Run on a fresh clone or container.

## Rollback Plan
- Delete generated `.env` and `.agent` folder and revert to manual setup.
