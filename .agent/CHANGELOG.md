# Changelog

All notable changes to the Agent Governance Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased] - 2026-02-18

### Fixed

- **AI Governance False Positives**: Added suppression rule #8 ("DIFF CONTEXT LIMITATIONS") to the AI system prompt, instructing the reviewer to assume code exists outside the visible diff window.
- **AI Governance False Positives**: Expanded `git diff` context from ±3 lines to ±10 lines (`-U10`) for more accurate AI review.
- **AI Governance False Positives**: Added suppression rules #9–#12 covering stdlib modules, sync/async verification, lazy initialization (ADR-025), and markdown `file://` URIs.
- **AI Governance False Positives**: Expanded `_validate_finding_against_source` validator with stdlib dependency detection, sync/async misclassification (checks `def` vs `async def`), lazy-init import recognition, and line-number drift detection (verifies cited lines match claims).
- **AI Governance False Positives**: Made finding validator always-on instead of gating behind `--thorough`; only full-file context augmentation remains `--thorough`-only.
- **JSON Extraction**: `extract_json_from_response` now returns raw bracket-matched content as a fallback instead of an empty string when no valid JSON can be parsed.
- **Integration Tests**: `Path.exists` mocks in `test_python_agent.py` no longer break DB schema lookup during `new-story`, `new-plan`, and `new-adr` commands.

### Added

- **Thorough AI Review**: New `--thorough` flag for `agent preflight --ai` enables full-file context augmentation (AST-based signature extraction) and post-processing validation to filter false positives. Uses more tokens but significantly reduces incorrect BLOCK verdicts.
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
