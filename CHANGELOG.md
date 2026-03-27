# Changelog

## [Unreleased] - INFRA-171
**Added**
- Explicit `testpaths` configuration in `.agent/pyproject.toml` to ensure discovery of consolidated tests.

**Changed**
- Identified 49 orphaned test files in `.agent/src/` for migration to top-level `.agent/tests/` directory.

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
**Security**
- Added automated PII scrubbing for per-section vector query strings in the runbook generation pipeline (INFRA-172).

**Added**
- INFRA-170: Deterministic Complexity Gates (File LOC > 500, Function > 50).
- AI Finding Cross-Validation: AI syntax claims verified via py_compile.

**Changed**
- Governance architecture: Transitioned from _governance_legacy.py to modular sub-package.
- Default Preflight Mode: Thorough analysis enabled by default; added --quick flag.

### Added
- **INFRA-165**: Introduced a modular, two-phase chunked generation pipeline for runbooks, including Phase 1 Skeleton and Phase 2 Block generation with JSON validation and OTel tracing.
- **INFRA-142**: Migrated search and git tools to dedicated modules with AST-aware symbol lookup and git history.
- **INFRA-142**: Migrated and consolidated search and git tools into dedicated domain modules. Added AST-aware `find_symbol` for semantic Python navigation and expanded git tools with history and blame support.
- **INFRA-163**: Added `--autoheal` flag to preflight command for autonomous governance and test failure remediation.
- **INFRA-162**: Enhanced DoD Compliance Gate (Gate 4) with deterministic verifiers for Impact Analysis completeness (`_gap_4f`) and ADR reference validation (`_gap_4g`).
- **INFRA-141**: Migrated filesystem and shell tools to dedicated domain modules and added `move_file`, `copy_file`, and `file_diff`.
- **INFRA-140**: Dynamic Tool Engine and Security. Introduces `agent/tools/dynamic.py` with `create_tool()` (AST security scan, path containment, hot-reload via `importlib`) and `import_tool()` (path-based load via `spec_from_file_location` for test hermiticity). Migrates dynamic tool creation from `backend/voice/tools/create_tool.py` to the shared core. Adds `agent/tools/custom/__init__.py` package and 6 unit tests in `agent/tools/tests/test_dynamic.py`. Includes runbook-generation reliability improvements: batch gate collect-then-fix loop, deterministic `[MODIFY]`-on-missing-file autohealing, configurable `--timeout` for AI requests (`AGENT_AI_TIMEOUT_MS`), `.agent/cache/` path exemption from S/R validation, and `__init__.py` path preservation fix in the AST parser (`_children_text` recurses into `strong`/`emphasis` tokens). Third-party library noise (`transformers`, `sentence_transformers`) suppressed at module-import level in `logger.py` via `set_verbosity_error()`. Story state transitions corrected: `agent implement` now sets `COMMITTED` (not `DONE`) on success.
- **INFRA-160**: `agent new-runbook` now injects the full JRN/ADR catalogue into the AI generation prompt. Before each generation attempt, the command scans `.agent/cache/journeys/` and `config.adrs_dir` and builds a structured list of up to 30 entries (most recent first, `id` + `title` only). This enables the AI panel to reference existing journeys and ADRs by ID in the generated runbook, which are then automatically back-populated into the story's `## Linked Journeys` / `## Linked ADRs` sections via `merge_story_links` (INFRA-158) — eliminating manual journey-gate fixes. Emits a `catalogue_injected` structured log event with `journey_count` and `adr_count`. Adds `build_journey_catalogue()` and `build_adr_catalogue()` helpers to `agent.commands.utils`. Gracefully no-ops when the relevant directories are absent.
- **INFRA-157**: New `agent decompose-story <STORY_ID>` command. Reads a split-request JSON produced by `agent new-runbook`, generates numbered child story files and a parent plan document, and marks the parent story `SUPERSEDED (see plan: ...)` in one atomic operation. Supports `--dry-run` to preview without writing, and is idempotent — re-running when output files already exist exits with a clear conflict error rather than overwriting. Extends `update_story_state` in `agent.commands.utils` with an optional `annotation` parameter. Fixes a pre-existing bug in `agent implement` where `yaml.safe_dump` silently stripped leading comment blocks (including Apache 2.0 license headers) from journey YAML files on every run. Also fixes the `agent preflight` test runner to invoke `.venv/bin/python` so all venv-installed dependencies (e.g. `mistune`) are available. 14 new tests.
- **INFRA-161**: `agent new-runbook` now runs a **DoD Compliance Gate** (Gate 4) after the S/R validation gate. Five deterministic verifiers check: (1) at least one test-file step, (2) a CHANGELOG.md step, (3) Apache-2.0 license headers on all `[NEW]` Python files, (4) OTel spans in commands/core steps when the story requires observability. Gaps are bundled into a single correction prompt and share the existing 3-attempt retry budget. Structured log events: `dod_compliance_fail`, `dod_compliance_pass`, `dod_correction_attempt`. OTel span: `dod_compliance_gate`. Adds `extract_acs`, `check_test_coverage`, `check_changelog_entry`, `check_license_headers`, `check_otel_spans`, `build_dod_correction_prompt` to `agent.commands.utils`. Also fixes `guards.py` code-gate false-positives: missing trailing newlines are now auto-corrected (warning, not error), and `test_*.py` files have implicit allowlists for `pytest`, `typer`, and other test-only imports. 13 new tests (8 unit, 5 integration).
- **INFRA-159**: `agent new-runbook` now validates every `<<<SEARCH` block in the generated runbook against the actual file content on disk before saving. If any block fails to match verbatim, the AI is re-prompted with the real file content and asked to self-correct (up to 2 retries). A `[MODIFY]` block targeting a missing file exits immediately with code 1. `[NEW]` blocks are exempt. Structured log events emitted: `sr_validation_pass`, `sr_validation_fail`, `sr_correction_attempt`, `sr_correction_success`, `sr_correction_exhausted`. File content included in correction prompts is scrubbed via `scrub_sensitive_data`. Adds `_lines_match`, `validate_sr_blocks`, and `generate_sr_correction_prompt` helpers to `agent.commands.utils`.
- **INFRA-158**: `agent new-runbook` now automatically back-populates the parent story's `## Linked ADRs` and `## Linked Journeys` sections with references found in the generated runbook. Only references resolvable to a local file (ADR markdown or journey YAML) are written; unresolvable references are skipped to prevent `agent implement` validation errors. Updates are idempotent across regeneration. Adds `extract_adr_refs()`, `extract_journey_refs()`, and `merge_story_links()` helpers to `agent.commands.utils`.
- **INFRA-155**: Hardened implement pipeline with code validation gates. Introduces `ValidationResult` dataclass in `guards.py` with `errors` (blocking) and `warnings` (non-blocking). Adds `validate_code_block()`, refactored `enforce_docstrings()` (nested function docstrings demoted to warnings), and `check_imports()` (validates dependencies against `pyproject.toml`). Integrates self-healing retry loop in `new-runbook` command. OpenTelemetry spans added to all validation functions.
- **INFRA-139**: Core Tool Registry and Foundation. Introduces `agent.tools` package with `ToolRegistry`, `Tool`, and `ToolResult` Pydantic models. Supports tool registration, O(1) lookup, category filtering, and governance-audited `unrestrict_tool()`. Includes 6 unit tests covering registration, duplicate rejection, filtering, audit logging, and error paths.
- **INFRA-121** (enhancement): Conditional trace-aware log formatting and automatic PII scrubbing. Adds `TraceAwareFormatter` to conditionally include `trace_id`/`span_id` in logs only when tracing is active. Adds `PiiScrubbingSpanProcessor` to automatically scrub PII-sensitive span attributes (prompts, completions, inputs, outputs) before export. Wires `initialize_telemetry()` into CLI startup. Includes 15 new unit tests.
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
