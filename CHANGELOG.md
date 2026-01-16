# Changelog

All notable changes to the Agent Governance Framework will be documented in this file.

## [Unreleased]

### Added
- **UI Tests Runner**: New `agent run-ui-tests` command to execute Maestro UI test flows.
- **Enhanced Implement Command**: Added `--apply` and `--yes` flags to `agent implement` for automatic code application.
- **Improved Impact Analysis**: Enhanced `agent impact` with dependency tracking using AST parsing for Python and regex for JavaScript.
- **Governance Commands**: New `agent panel` and `agent preflight` Python implementations.
- **Consultative Mode**: `agent panel` now acts as a consultative board rather than a gatekeeper.

### Changed
- **Documentation Structure**: Relocated `docs/` to `.agent/docs/` for better encapsulation.

## [0.2.0] - 2026-01-12

### Added
- **Smart AI Router**: Python implementation of `SmartRouter` to dynamically select models based on cost, tier, and context window limits.
- **Router Configuration**: New `.agent/router.yaml` file for defining model tiers and pricing.
- **Token Management**: `TokenManager` class with `tiktoken` support for accurate accounting.
- **Unit Tests**: comprehensive testing suite for routing logic (`tests/core/test_router.py`).
- **Workflow Optimization**: Refactored workflows to be simple wrappers around Python CLI commands, reducing token usage and ensuring logic parity.
- **Runbook Template**: Extracted runbook structure to `.agent/templates/runbook-template.md`.
- **System Instructions**: Added `GEMINI.md` and `.github/copilot-instructions.md` for AI agent guidance.
- **Story Workflow**: Added `workflows/story.md` for creating stories from conversation context.
- **Governance Enforcement**: Implemented strict state transitions (Plan: APPROVED -> Story: COMMITTED -> Runbook: ACCEPTED) to ensure quality gates are respected.
- **Smart Commit**: Added `agent commit --ai` to auto-generate conventional commit messages and infer story IDs.
- **Comprehensive Documentation**: Created `/docs` directory with 9 detailed guides (~4,700 lines):
  - `getting_started.md` - Installation and first workflows
  - `commands.md` - Complete CLI reference with examples
  - `governance.md` - AI panel roles and review process
  - `workflows.md` - Story-driven development patterns
  - `configuration.md` - Customization and CI/CD integration
  - `ai_integration.md` - Provider setup and token optimization
  - `rules_and_instructions.md` - Creating custom governance rules
  - `troubleshooting.md` - Common issues and solutions
  - `README.md` - Documentation index and navigation

### Changed
- **Config Relocation**: Moved `agents.yaml` and `router.yaml` to `.agent/etc/` for better organization.
- **SDK Migration**: Migrated from deprecated `google-generativeai` to modern `google-genai` SDK.
- **Dependency Update**: Updated `openai`, `typer`, `rich`, `pydantic`, `tiktoken`, and `google-genai` to latest stable versions.
- **Documentation**: Updated `SMART_AI_ROUTER.md` to reflect the actual Python implementation.
- **Project Structure**: Updated `.gitignore` to track agent artifacts while ignoring system files.
- **README.md**: Completely rewritten root README with quick start guide and links to comprehensive documentation.
- **Installation**: Corrected all documentation to use `pip install -e .agent/` with `pyproject.toml` instead of non-existent `requirements.txt`.

### Removed
- **Breaking Change**: Removed `agent plan` command - it had backwards workflow (tried to generate plans FROM stories instead of stories FROM plans).

## [0.1.0] - 2026-01-11

### Added
- **Native Python AI Integration**: Ported all AI logic from legacy Bash scripts to `src/agent/core/ai.py`.
- **New Command**: `agent new-runbook <story_id>` - Generates structured runbooks using AI.
- **New Command**: `agent implement <runbook_id>` - AI-driven implementation assistant.
- **New Command**: `agent match-story --files ...` - AI-powered story matching for atomic commits.
- **Enhanced Preflight**: `agent preflight --ai` now convenes a full "Governance Council" of 9 AI roles (Architect, Security, QA, etc.) for comprehensive review.
- **Smart Chunking**: Automated diff chunking for handling large changesets even on limited context windows (GitHub CLI).
- **Multi-Provider Support**: Seamless support for Google Gemini (`gemini-1.5-pro`), OpenAI (`gpt-4o`), and GitHub CLI fallback.
- **Log Persistence**: Preflight reports are now saved to `.agent/logs/`.

### Changed
- Refactored `agent` shim script to route commands to the Python CLI.
- Updated `pyproject.toml` dependencies to include `google-generativeai` and `google-genai`.

### Removed
- **Breaking Change**: Removed the `-v` shorthand for `--version` to align with standard convention (verbose flag reserve).
- Deprecated usage of `ops_ai.sh` (legacy bash AI logic).

### Added
- **Global Linting**: `agent lint` now supports scanning arbitrary directories and files (e.g., `agent lint web/`).
- **Path-Based Dispatch**: Automatically selects the correct linter (`ruff`, `shellcheck`, `eslint`) based on file extensions found in the target path.
- **Recursive Scanning**: Added `agent lint --all` to scan the entire repository recursively, respecting `.gitignore` where possible.
- **JS/TS Support**: Added support for linting JavaScript and TypeScript files using `eslint` (via `npx` or local `node_modules`).
