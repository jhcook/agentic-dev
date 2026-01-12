# Changelog

All notable changes to the Agent Governance Framework will be documented in this file.

## [Unreleased] - 2026-01-11

### Added
- **Native Python AI Integration**: Ported all AI logic from legacy Bash scripts to `src/agent/core/ai.py`.
- **New Command**: `agent plan <story_id>` - Generates implementation plans using AI.
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
