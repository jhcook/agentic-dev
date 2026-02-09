# Changelog

All notable changes to the Agent Governance Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased] - 2026-02-09

### Fixed
- **JSON Extraction**: `extract_json_from_response` now returns raw bracket-matched content as a fallback instead of an empty string when no valid JSON can be parsed.
- **Integration Tests**: `Path.exists` mocks in `test_python_agent.py` no longer break DB schema lookup during `new-story`, `new-plan`, and `new-adr` commands.

### Changed
- **Config**: `backup_config()` now lazily creates `backups_dir` on first use, consistent with `logs_dir` initialisation in `logger.py`.
- **Implement**: Removed duplicate `update_story_state` from `implement.py`; canonical version lives in `core/utils.py`.
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
