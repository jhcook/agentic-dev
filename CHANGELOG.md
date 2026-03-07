# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Decomposed `commands/implement.py` into focused modules under `core/implement/`:
  - `circuit_breaker.py`: Tracks LOC edits and enforces thresholds.
  - `guards.py`: Handles docstring enforcement and safe-apply size guards.
  - `orchestrator.py`: Manages path resolution, block parsing, and chunking logic.
- Retained `commands/implement.py` as a facade re-exporting symbols for backward compatibility with existing tests.
- Fixed uninitialised-variable bug in `apply_chunk` logic.
- **`agent implement` reliability**: Runbooks with explicit `File:`/`<<<SEARCH` blocks are now applied directly without AI regeneration, making them deterministic and CI-safe.
- **`resolve_path` trusted-prefix fix** (INFRA-109): Paths starting with `.agent/`, `agent/`, `backend/`, `web/`, or `mobile/` now bypass fuzzy filename search, preventing silent misdirection to same-named files elsewhere in the repo.

### Added
- Unit tests for governance roles and package facade.
- New `agent.core.governance` package structure.

### Changed
- Refactor: Extract governance roles module from legacy monolith into `agent.core.governance.roles` (INFRA-101).
- Decomposed monolithic `core/governance.py` into a package structure `core/governance/`.

### Changed
- refactor: decompose monolithic governance module into package structure (INFRA-101)
- refactor: extract governance roles management into `core.governance.roles` (INFRA-101)

### Added
- Decomposed AI service into modular providers using Strategy pattern (INFRA-100).
- New `AIProvider` protocol and standard error types in `core/ai/protocols.py`.
- Isolated streaming and retry logic with exponential backoff in `core/ai/streaming.py`.
- Unified provider registry in `core/ai/providers.py`.

### AI Core
- Decomposed monolithic `AIService` into a modular, provider-based architecture using the Strategy pattern (INFRA-100).
- Introduced `AIProvider` Protocol for standardized model interactions.
- Extracted retry and backoff logic into a dedicated `streaming` module.
- Consolidated provider dispatch logic in `providers.py` to support future multi-backend extensibility.

### Added
- INFRA-107: Added targeted codebase introspection to `agent new-runbook`.
- New `ContextLoader` methods: `_load_targeted_context`, `_load_test_impact`, `_load_behavioral_contracts`.
- Automatic Test Impact Matrix and Behavioral Contract extraction for runbook generation.

### Changed
- Increased default source context budget to 16,000 characters.
- Included `tests/` directory in broad source outlines.

### Added
- **INFRA-097**: Configurable agent personality for `agent console` via `agent.yaml`.
  - Added `console.personality_file` and `console.system_prompt` config keys.
  - Support for repo-specific context files (e.g., `GEMINI.md`) in the console system prompt.
  - Path traversal protection for `personality_file` (must resolve within repo root).
  - Graceful fallback to existing hardcoded prompt when no config is set.
  - Debug logging for prompt composition (`system_prompt.personality_loaded`).
- **INFRA-096**: Safe implementation apply — search/replace format, source context injection, and file size guard.
  - Added `parse_search_replace_blocks()` parser for `<<<SEARCH/===/>>>` format.
  - Added source context injection (`extract_modify_files` + `build_source_context`) to AI prompts.
  - Added `apply_search_replace_to_file()` for surgical, no-partial-apply edits.
  - Added file size guard to `apply_change_to_file()` — rejects full-file overwrites for files >200 LOC.
  - Added `--legacy-apply` CLI flag for escape-hatch bypass (audit-logged via SOC2).
  - Updated AI system prompts to instruct search/replace for existing files.
- **INFRA-095**: Implemented micro-commit implementation loop and circuit breaker in `implement.py`.
  - Added line-level edit distance tracking per implementation step.
  - Added save-point micro-commits after each successful runbook step application.
  - Implemented 200 LOC warning and 400 LOC hard circuit breaker for implementation runs.
  - Added automatic follow-up story generation and plan linkage when the circuit breaker is triggered.
  - Integrated OpenTelemetry spans for micro-commit steps and circuit breaker events.

### Fixed
- N/A

### Changed
- Refactored `agent implement` chunked processing loop to support atomic save points and size enforcement.
