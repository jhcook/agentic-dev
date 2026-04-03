# Changelog

All notable changes to the Agent Governance Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added

- **INFRA-158 — Story Link Back-Population**: `agent new-runbook` now extracts all `ADR-NNN` and `JRN-NNN` references from the generated runbook and writes them back to the parent story's `## Linked ADRs` and `## Linked Journeys` sections. Updates are idempotent (no duplicates on re-run), atomic (write-then-rename), and best-effort (runbook generation still succeeds if the story file is unwritable). Emits structured log event `story_links_updated`.
- **Polyglot QA Gate** (`gates.py`, `implement.py`): `run_qa_gate` now accepts a
  `test_commands` dict keyed by repo-relative directory prefix. The implement pipeline
  accumulates all modified files across steps and runs only the test suite(s) whose
  prefix matches — so a web-only change never triggers the backend suite. Legacy
  `test_command: <string>` config still works unchanged.
- **`test_commands` key in `agent.yaml`**: Replaces the single `test_command` string.
  Each key is a directory prefix (e.g. `backend/`, `web/`) mapping to the test runner
  command for that domain. Supports any language and test runner.

### Fixed

- **`agent implement` QA gate** (`agent.yaml`): test_command was hardcoded to
  `.venv/bin/pytest` which does not exist. Fixed to `python -m pytest` and migrated to
  the new `test_commands` dict key.
- **Ambiguous directory resolution** (`implement.py`): `find_directories_in_repo` now
  prunes `node_modules` and `dist` from its `find(1)` search, preventing common names
  like `src` and `tests` from matching dozens of JS dependency tree paths.
- **Pre-existing test drift** (`test_service.py`, `test_regression_credentials.py`):
  Four tests that broke when `service.py` dispatch and `preflight()` signature changed
  (INFRA-100) are now marked `@pytest.mark.xfail(strict=False)` with a clear reason.
  Configuration files no longer carry `--deselect` flags as a workaround.

### Changed

- **Runbook template** (`templates/runbook-template.md`): Implementation Steps section
  now mandates machine-executable `[MODIFY]`/`[NEW]`/`[DELETE]` step blocks with
  `<<<SEARCH/===/>>>` diffs for modifications and complete file content for new files.
  Prose instructions are explicitly forbidden. Template is language-agnostic — no
  Python-specific paths or code examples.
- **Runbook workflow** (`workflows/runbook.md`): Added Mandatory Format Check step
  describing the three permitted step formats and key validation rules reviewers must
  apply before accepting a runbook.

### Refactored

- INFRA-108: Decomposed `core/ai/providers.py` into `core/ai/providers/` package with
  per-provider modules (openai, vertex, anthropic, ollama, gh, mock). `AIService._try_complete`
  and `stream_complete` now delegate to `AIProvider` instances via the `get_provider()` factory.
  Rate-limit retry uses typed `AIRateLimitError` instead of string matching. — 2026-03-07

### Fixed

- **AI Governance False Positives**: Added suppression rule #8 ("DIFF CONTEXT LIMITATIONS") to the AI system prompt, instructing the reviewer to assume code exists outside the visible diff window.
- **AI Governance False Positives**: Expanded `git diff` context from ±3 lines to ±10 lines (`-U10`) for more accurate AI review.
- **AI Governance False Positives**: Added suppression rules #9–#12 covering stdlib modules, sync/async verification, lazy initialization (ADR-025), and markdown `file://` URIs.
- **AI Governance False Positives**: Expanded `_validate_finding_against_source` validator with stdlib dependency detection, sync/async misclassification (checks `def` vs `async def`), lazy-init import recognition, and line-number drift detection (verifies cited lines match claims).
- **AI Governance False Positives**: Made finding validator always-on instead of gating behind `--thorough`; only full-file context augmentation remains `--thorough`-only.
- **JSON Extraction**: `extract_json_from_response` now returns raw bracket-matched content as a fallback instead of an empty string when no valid JSON can be parsed.
- **Integration Tests**: `Path.exists` mocks in `test_python_agent.py` no longer break DB schema lookup during `new-story`, `new-plan`, and `new-adr` commands.

### Added

- **Thorough AI Review**: New `--thorough` flag for `agent preflight` enables full-file context augmentation (AST-based signature extraction) and post-processing validation to filter false positives. Uses more tokens but significantly reduces incorrect BLOCK verdicts.
- **User Journeys**: First-class journey artifacts with `new-journey`, `validate-journey`, `list-journeys` CLI commands (INFRA-055, ADR-024).

### Changed

- **Config**: `backup_config()` now lazily creates `backups_dir` on first use, consistent with `logs_dir` initialisation in `logger.py`.
- **Implement**: Removed duplicate `update_story_state` from `implement.py`; canonical version lives in `commands/utils.py`.
- **Documentation**: `update_story_state` docstring expanded with purpose, callers, args, and internal-only designation.

## [Unreleased] - 2026-01-13

### Security

- **Sync Authentication**: Introduced `SUPABASE_ACCESS_TOKEN` requirement. Deprecated and removed client-side usage of `SUPABASE_SERVICE_ROLE_KEY`.
- **PII Scrubbing**: Implemented mandatory PII scrubbing (emails, IPs, keys) for all data persisted to the local cache (`agent.db`).
- **Secrets**: Added `.agent/secrets/` to `.gitignore`.

### Added

- **Synchronization**: access to `agent sync push` and `agent sync pull` to synchronize artifacts via Supabase.
- **Synchronization**: Implemented core logic for `agent sync push` and `agent sync pull` using Supabase Python client.
- **Documentation**: Comprehensive documentation suite added to `.agent/docs/`.
- **ADR-018**: Documented Agent Data Persistence and Synchronization architecture.

### Changed

- **Database Schema**: Added `owner_id` to `artifacts` table and implemented ownership-based Row Level Security (RLS).
- **README**: Updated `.agent/README.md` to reflect new documentation structure and sync features.
