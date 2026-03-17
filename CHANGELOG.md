# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **INFRA-139**: Core Tool Registry and Foundation. Introduces `agent.tools` package with `ToolRegistry`, `Tool`, and `ToolResult` Pydantic models. Supports tool registration, O(1) lookup, category filtering, and governance-audited `unrestrict_tool()`. Includes 6 unit tests covering registration, duplicate rejection, filtering, audit logging, and error paths.
- **INFRA-148**: Parser robustness and path unescaping. Adds `_unescape_path` helper to strip markdown formatting from file paths (bold, backticks, backslash-escaped underscores). Implements balanced fence detection in `_mask_fenced_blocks` to prevent premature closure with nested code fences. Adds debug logging for parsing failures. Introduces `--stage` and `--commit` flags to `agent implement` — `--apply` now writes files without staging or committing; `--stage` stages modified files via `git add`; `--commit` auto-commits per step (implies staging). Includes 15 new unit tests covering path unescaping, balanced fences, and extraction functions.
- **INFRA-136**: Execution tracing and scope guardrails. Adds `_check_scope()` to `Orchestrator` to block file modifications not declared in the runbook's `[MODIFY]`/`[NEW]`/`[DELETE]` sections. Wraps `apply_chunk()` in Langfuse/OTLP trace spans with `story_id` and `step_index` attributes. Computes hallucination rate (`scope_violations / total_blocks`). Supports `<!-- cross_cutting: true -->` annotation to relax scope for shared files. Fixes runbook schema parser to mask fenced code blocks before scanning for operation headers.
- **INFRA-138**: Canonical CWD path resolution. Adds `resolve_repo_path()` utility to anchor all file operations to `config.repo_root`, eliminating CWD-dependent failures when the CLI is invoked from `.agent/`. Fixes `resolver.py`, `orchestrator.py`, and re-enables parent directory validation in `ModifyBlock` using the canonical resolver.
- **INFRA-135**: Dynamic Rule Retrieval (Rule Diet). Replaces static 3000-char rule truncation with semantic retrieval via ChromaDB. Classifies `.agent/rules/` into core (always-included: 000-004) and contextual (retrieved on demand). Fixes ChromaDB fallback regression so local vector DB activates when NotebookLM is unavailable. Adds structured `rule_retrieval` log events for SOC2 compliance.
- **INFRA-134**: Shift-left runbook validation with Pydantic models. Replaces regex-based `validate_runbook_schema()` with structured Pydantic validators (`RunbookSchema`, `ModifyBlock`, `NewBlock`, `DeleteBlock`). Includes a self-correction retry loop (max 3 attempts) for AI-generated runbooks, OpenTelemetry tracing for validation latency, and dedicated unit tests.
- **INFRA-098**: Unified the agent interface layer across TUI and Voice by introducing `agent.core.session.AgentSession` which relies entirely on protocol-based AIProvider and exposes a unified schema for tools.
- **INFRA-126**: Intergrated standard retry logic and telemetry to verification orchestrator handling of rewrite requests.
- **INFRA-121**: OpenTelemetry tracing for LLM flows and Langfuse integration.
- **INFRA-125**: Standardized robust `@with_retry` decorator and utilities (sync and async) with OpenTelemetry backoff instrumentation per ADR-012.

### Changed
- **INFRA-119**: Implemented strict JSON schema validation for LLM outputs with automatic retry loop. This includes Pydantic models for AgentAction and Finish, and robust JSON recovery parsing using ReActJsonParser.

### Refactored
- **INFRA-110**: Decomposed `check.py` command into modular components in `core/check/`, separating concerns like preflight orchestration, reporting, syncing, and testing.
- **INFRA-105**: Decomposed monolithic `commands/onboard.py` into a thin CLI facade plus a new module `core/onboard/steps.py`. Extracted standalone functions for checking dependencies, GitHub auth, and creating directories, making them independently testable.
- **INFRA-103**: Decomposed `commands/check.py` (1,768 LOC) into a thin CLI
  facade plus `core/check/system.py` (credential validation, story schema,
  journey linkage) and `core/check/quality.py` (journey coverage). All existing
  callers and mock-patch paths remain unaffected via re-exports. New unit tests
  added in `tests/core/check/`.

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

## Copyright

Copyright 2026 Justin Cook
