# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
