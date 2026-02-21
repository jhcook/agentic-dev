# INFRA-004: Distributed Cache Synchronization with SQLite and Supabase

## State
COMMITTED

## Problem Statement
Multiple remote developers are working on Plans, Stories, and Runbooks stored in `.agent/cache/`, but currently lack a real-time synchronization mechanism to prevent collisions and ensure data consistency. While the `agent` CLI can export these artifacts as markdown to Git (the ultimate source of truth), the workflow is too static for dynamic, collaborative development. Developers need a more responsive system that allows them to:
1. Work with artifacts locally without constant network connectivity
2. Synchronize changes with a central database to share updates in real-time
3. Resolve conflicts when multiple developers modify the same artifact
4. Maintain Git as the authoritative source while enabling faster iteration

## User Story
As a **remote developer**, I want a **git-like distributed synchronization system for Plans, Stories, and Runbooks** so that I can **work locally on artifacts, push my changes to a shared database, and pull updates from other developers in real-time without file collisions**.

## Acceptance Criteria

### Core Synchronization
- [ ] **Local SQLite Database**: `.agent/cache/` artifacts (Plans, Stories, Runbooks) are stored in a local SQLite database with full CRUD operations
- [ ] **Supabase Integration**: System can connect to a Supabase (PostgreSQL) database as the "origin" remote
- [ ] **Push Operation**: `env -u VIRTUAL_ENV uv run agent sync push` command uploads local changes to Supabase, resolving conflicts automatically or prompting for manual resolution
- [ ] **Pull Operation**: `env -u VIRTUAL_ENV uv run agent sync pull` command downloads remote changes from Supabase and merges them into the local SQLite database
- [ ] **Sync Status**: `env -u VIRTUAL_ENV uv run agent sync status` command shows which artifacts have local changes, remote changes, or conflicts
- [ ] **Conflict Resolution**: When conflicts occur (same artifact modified both locally and remotely), system provides clear conflict markers and resolution workflow

### Data Model
- [ ] **Version Tracking**: Each artifact (Plan, Story, Runbook) has a version number and last-modified timestamp
- [ ] **Change History**: System maintains a commit-like history of changes to each artifact
- [ ] **Author Attribution**: Changes are attributed to specific developers (using Git user config or SUPABASE_USER)
- [ ] **State Preservation**: Current state fields (`Status: APPROVED`, `State: COMMITTED`, etc.) are preserved and synchronized

### Git Integration
- [ ] **Markdown Export**: `env -u VIRTUAL_ENV uv run agent sync export` command generates markdown files from SQLite to `.agent/cache/` for Git commits (existing functionality preserved)
- [ ] **Markdown Import**: `env -u VIRTUAL_ENV uv run agent sync import` command read markdown files from STDIN or ARGV comma-delimited string of paths, validates them, and populate SQLite database. 
- [ ] **Create New Artifacts**: `env -u VIRTUAL_ENV uv run agent new-plan`, `env -u VIRTUAL_ENV uv run agent new-story`, `env -u VIRTUAL_ENV uv run agent new-runbook` commands create new artifacts in SQLite. SQLite syncs to remote before it issues an artifact id.
- [ ] **Git as Source of Truth**: On fresh clone, `env -u VIRTUAL_ENV uv run agent sync import` initializes the local database from markdown files
- [ ] **Bidirectional Sync**: Changes can flow: SQLite ↔ Markdown ↔ Git ↔ Supabase

### Developer Experience
- [ ] **Offline Mode**: Developers can work offline; `push`/`pull` operations queue until connectivity is restored
- [ ] **Configuration**: `.agent/etc/sync.yaml` defines Supabase connection details (URL, anon key, table schema)
- [ ] **First-Time Setup**: `env -u VIRTUAL_ENV uv run agent sync init` command initializes local database and configures remote connection
- [ ] **Dry Run**: `env -u VIRTUAL_ENV uv run agent sync push --dry-run` and `env -u VIRTUAL_ENV uv run agent sync pull --dry-run` show what would change without applying changes

### Non-Functional Requirements
- **Performance**: Local SQLite operations complete in <100ms; sync operations handle 1000+ artifacts efficiently
- **Security**: 
  - Supabase API keys stored in environment variables or encrypted config
  - Row-level security (RLS) policies on Supabase ensure developers only access authorized artifacts
  - PII scrubber applies to synchronized data
- **Compliance**: 
  - Audit log of all sync operations (who, what, when)
  - GDPR compliance: ability to purge developer data on request
- **Observability**: 
  - Structured logging for all sync events
  - Metrics: sync duration, conflict rate, artifact count
  - OpenTelemetry tracing for distributed operations

## Linked ADRs
- ADR-001: Git-like Distributed Synchronization Architecture
- ADR-002: SQLite as Local Cache Layer
- ADR-003: Supabase for Real-Time Collaboration

## Impact Analysis Summary
**Components Touched:**
- New: `.agent/src/agent/sync/` module (push, pull, status, conflict resolution)
- New: `.agent/src/agent/db/` module (SQLite schema, migrations, ORM)
- Modified: `.agent/src/agent/commands/` (add sync commands)
- Modified: All artifact CRUD operations (Plans, Stories, Runbooks) to use SQLite
- New: `.agent/etc/sync.yaml` configuration file
- New: Database schema in `.agent/cache/agent.db`

**Workflows Affected:**
- Story creation: `env -u VIRTUAL_ENV uv run agent new-story` writes to SQLite and auto-pushes to remote
- Plan creation: `env -u VIRTUAL_ENV uv run agent new-plan` writes to SQLite and auto-pushes to remote
- Runbook generation: `env -u VIRTUAL_ENV uv run agent new-runbook` writes to SQLite and auto-pushes to remote
- CI/CD: Add `env -u VIRTUAL_ENV uv run agent sync pull` before preflight checks to ensure latest state

**Risks Identified:**
- **Data Loss**: Improper conflict resolution could overwrite changes
- **Schema Drift**: SQLite and Supabase schemas must stay synchronized
- **Migration Complexity**: Existing markdown-based workflows need migration path
- **Network Dependency**: Sync failures could block workflows if not handled gracefully
- **Concurrent Writes**: Race conditions if multiple processes access SQLite simultaneously

## Test Strategy
1. **Unit Tests**:
   - SQLite CRUD operations for all artifact types
   - Conflict detection and resolution logic
   - Markdown export/import round-trip consistency
2. **Integration Tests**:
   - Full push/pull cycle with mock Supabase instance
   - Concurrent updates from multiple developers (simulate with threads)
   - Offline mode: queue operations, replay on reconnect
3. **End-to-End Tests**:
   - Developer A creates story → pushes → Developer B pulls → sees story
   - Conflict scenario: Both modify same story → merge resolution
   - Git integration: Export → commit → fresh clone → import → verify
4. **Performance Tests**:
   - Sync 1000 artifacts (measure time, memory)
   - Concurrent access with 10 simulated developers
5. **Security Tests**:
   - Verify RLS policies prevent unauthorized access
   - Ensure API keys not logged or committed

## Rollback Plan
1. **Phase 1 (Additive)**: SQLite layer is optional; markdown still works
   - Rollback: Disable sync commands, continue using markdown
2. **Phase 2 (Migration)**: Existing markdown → SQLite import
   - Rollback: Re-export all SQLite data to markdown, delete `.agent/cache/agent.db`
3. **Phase 3 (Supabase)**: Remote sync enabled
   - Rollback: Disable remote sync in config, operate in local-only mode
4. **Emergency**: Restore from Git (source of truth)
   - `git checkout main -- .agent/cache/`
   - `env -u VIRTUAL_ENV uv run agent sync import` to rebuild database
