# Changelog

All notable changes to the Agent Governance Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
