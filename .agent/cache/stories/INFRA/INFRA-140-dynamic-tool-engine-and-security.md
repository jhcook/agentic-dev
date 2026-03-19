# INFRA-140: Dynamic Tool Engine and Security

## State

COMMITTED

## Problem Statement

The `ToolRegistry` foundation (INFRA-139) is complete. The Voice agent has a dynamic tool creation capability in `backend/voice/tools/create_tool.py` that is isolated from the Console. This story migrates the AST-based security scanner, path containment, and hot-reload logic into the core `agent/tools/dynamic.py`, making dynamic tool creation a shared capability registered via `ToolRegistry`. `agent/tools/dynamic.py` does not yet exist on disk.

Parent: INFRA-098

## User Story

As a **Platform Developer**, I want **dynamic tool creation with AST security scanning in the core ToolRegistry** so that **both Console and Voice can safely create, import, and hot-reload tools at runtime.**

## Acceptance Criteria

- [ ] **AC-1**: `agent/tools/dynamic.py` implements `create_tool()` with AST-based security scanning (rejecting `eval`, `exec`, `subprocess`, `os.system`, `os.popen`).
- [ ] **AC-2**: Path containment enforces tools are created only within `.agent/src/agent/tools/custom/`.
- [ ] **AC-3**: Hot-reload via `importlib.import_module()` / `importlib.reload()` makes newly created tools immediately available.
- [ ] **AC-4**: `# NOQA: SECURITY_RISK` comment in tool source code bypasses the AST security scan.
- [ ] **AC-5**: `import_tool()` loads a tool from `custom/` into the active `ToolRegistry` session.
- [ ] **Negative Test**: Creating a tool with `eval()` in the source is rejected with a clear `SecurityError`.
- [ ] **Negative Test**: Creating a tool outside `custom/` is rejected with a path traversal error.

### Runbook Generation Reliability (implemented this session)

- [x] **AC-R1**: All validation gates (schema, code, S/R, DoD) run in collect mode on every attempt; a single combined correction prompt is sent per retry — no gate short-circuits mid-pass.
- [x] **AC-R2**: `[MODIFY]` blocks targeting files that do not yet exist are deterministically autohealed (converted to `[NEW]`) as a free pass that does not consume a retry slot.
- [x] **AC-R3**: Files known to require `[NEW]` are accumulated in `known_new_files` and baked into the base user prompt for all subsequent retries.
- [x] **AC-R4**: Files under `.agent/cache/` (stories, plans, runbooks) are silently exempt from S/R validation — runbooks must not include steps that modify meta-files.
- [x] **AC-R5**: System prompt instruction 13 explicitly forbids generating `[MODIFY]` or `[NEW]` steps for `.agent/cache/` paths.
- [x] **AC-R6**: `agent new-runbook` accepts a `--timeout` option (default 180 s) that configures the AI request timeout uniformly across all providers via `AGENT_AI_TIMEOUT_MS`.
- [x] **AC-R7**: Exact story file path is injected into the user prompt to prevent AI path hallucination.
- [x] **AC-R8**: `_children_text` in `parser.py` recurses into `strong`/`emphasis` tokens to preserve `__dunder__` path segments (fixes `__init__.py` being written as `**init**.py`).
- [x] **AC-R9**: Third-party loggers (`transformers`, `sentence_transformers`, `huggingface_hub`) are suppressed to ERROR at module-import time in `logger.py`, eliminating the "layers were not sharded" noise. A friendly `ℹ️  Populating shards in vector index...` INFO log replaces it.
- [x] **AC-R10**: `_load_targeted_context` path extraction uses a prefix-agnostic regex — any backtick-quoted path containing at least one `/` is resolved. Hardcoded prefix whitelist (`.agent/`, `src/`, `backend/`) removed to support arbitrary repo layouts.
- [x] **AC-R11**: `AGENT_AI_TIMEOUT_MS` is read at call time for OpenAI and Anthropic providers in `_try_complete`, not baked in at client construction. The `--timeout` flag now takes effect for all providers uniformly.
- [x] **AC-R12**: `_try_complete` intercepts `ReadTimeout` / `TimeoutException` from any provider SDK and raises a clean `TimeoutError` with a one-liner message and retry hint instead of propagating the full httpx stacktrace.
- [x] **AC-R13**: `new_runbook` in `runbook.py` catches `TimeoutError` from the AI service and prints a clean `❌` one-liner to stderr before exiting, suppressing the raw exception trace.
- [x] **AC-R14**: `main.py` introduces a `main()` entry-point wrapper that catches all unhandled exceptions across every `agent` subcommand and displays a clean `❌ ExceptionType: message` one-liner to stderr. Full traceback available via `-v` or `AGENT_VERBOSE=1`.
- [x] **AC-R15**: `pyproject.toml` entry point updated from `agent.main:app` to `agent.main:main` so the top-level error handler is active for all installed invocations.

## Non-Functional Requirements

- Security: AST scan is the primary security gate — pure stdlib (`os`, `ast`, `importlib`), no framework dependency.
- Compliance: Structured log event emitted for every `create_tool` and `import_tool` invocation.
  > **Note**: `create_tool` and `import_tool` are `[NEW]` files created by the INFRA-140 runbook. Structured logging is specified in the runbook and will be implemented as part of that apply step, not in the current commit.

## Linked ADRs

- ADR-043: Tool Registry Foundation
- ADR-044: Global Exception Handler at CLI Entry Point

## Linked Journeys

- JRN-031: Voice Agent Tool Integration
- JRN-051: JRN-051-import-custom-voice-tool

## Impact Analysis Summary

Components touched:
- `.agent/src/agent/tools/dynamic.py` (NEW) — core dynamic tool engine
- `.agent/src/agent/tools/custom/__init__.py` (NEW) — custom tools package
- `.agent/src/agent/tools/tests/test_dynamic.py` (NEW) — 6 unit tests
- `.agent/src/backend/voice/tools/create_tool.py` (MODIFIED) — delegated to core engine
- `.agent/src/agent/commands/runbook.py` (MODIFIED) — batch gate loop, autohealing, `--timeout`, cache exemption, INFO log at vector index load
- `.agent/src/agent/commands/utils.py` (MODIFIED) — `validate_sr_blocks` returns structured mismatch, `.agent/cache/` skip
- `.agent/src/agent/commands/implement.py` (MODIFIED) — story state `DONE` → `COMMITTED`
- `.agent/src/agent/commands/tests/test_sr_validation.py` (MODIFIED) — updated for new mismatch contract
- `.agent/src/agent/core/ai/service.py` (MODIFIED) — `AGENT_AI_TIMEOUT_MS` respected by all providers
- `.agent/src/agent/core/implement/parser.py` (MODIFIED) — `_children_text` recurses into `strong`/`emphasis`; `_unescape_path` safety regex
- `.agent/src/agent/core/logger.py` (MODIFIED) — third-party verbosity suppressed at import time via `set_verbosity_error()`
- `.agent/src/agent/core/context.py` (MODIFIED) — `ia_pattern` regex no longer requires hardcoded path prefix; any backtick-quoted path with a `/` is captured (AC-R10)
- `.agent/src/agent/core/ai/service.py` (MODIFIED) — `AGENT_AI_TIMEOUT_MS` read at call time for OpenAI/Anthropic; `ReadTimeout` converted to clean `TimeoutError` in `_try_complete` (AC-R11, AC-R12)
- `.agent/src/agent/commands/runbook.py` (MODIFIED) — `TimeoutError` caught and printed as clean one-liner before exit (AC-R13)
- `.agent/src/agent/main.py` (MODIFIED) — `main()` wrapper with top-level exception handler; all uncaught exceptions formatted as clean one-liners (AC-R14)
- `.agent/pyproject.toml` (MODIFIED) — entry point `agent.main:app` → `agent.main:main` (AC-R15)

Workflows affected: Dynamic tool creation and hot-reload lifecycle; runbook generation reliability.
Risks identified: Migration is pure stdlib — no LangChain dependency in core logic.


## Test Strategy

### Dynamic Tool Engine (AC-1 – AC-5 + Negative Tests)

- Unit tests for `_security_scan()` with each forbidden pattern (`eval`, `exec`, `subprocess`, `os.system`, `os.popen`) and the `# NOQA: SECURITY_RISK` bypass.
- Unit tests for path containment enforcement (outside `custom/` → error).
- Integration test: create → import → execute a dynamic tool end-to-end.

### Runbook Generation Reliability (AC-R1 – AC-R15)

- **AC-R10 (context regex)**: `test_context_loader.py` — `test_existing_file_included`, `test_missing_file_marked_not_found`, `test_bare_filenames_are_excluded` all pass.
- **AC-R11 (timeout propagation)**: Manual smoke test — `agent new-runbook <ID> --timeout 300` confirmed; timeout value is read at call time in `_try_complete` for all providers.
- **AC-R12–R13 (clean timeout error)**: Unit test mocking `httpx.ReadTimeout` injected into `_try_complete`; asserts `TimeoutError` is raised with the hint string. Integration: the 180 s timeout error in the previous INFRA-142 run now surfaces as a single `❌` line.
- **AC-R14–R15 (global exception handler)**: Unit test calling `main()` via `subprocess` with a command that raises an unhandled `RuntimeError`; asserts exit code 1 and `❌ RuntimeError:` on stderr with no traceback.

## Rollback Plan

Delete `dynamic.py` and `custom/` — no existing code depends on them yet.

## Copyright

Copyright 2026 Justin Cook
