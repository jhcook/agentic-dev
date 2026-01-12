# ADR-001: Git-like Distributed Synchronization Architecture

## Status
Proposed

## Context
The `.agent` system manages critical governance artifacts (Plans, Stories, Runbooks) that are currently stored as markdown files in `.agent/cache/`. Multiple remote developers need to collaborate on these artifacts simultaneously, but the current file-based approach has several limitations:

1. **No Real-Time Sync**: Developers must manually push/pull markdown files via Git, which is slow and error-prone
2. **Collision Risk**: Two developers can modify the same artifact simultaneously, leading to merge conflicts
3. **No Conflict Resolution**: Git merge conflicts in markdown are difficult to resolve, especially for structured data
4. **Discovery Latency**: Developers don't know what others are working on until they push to Git
5. **State Enforcement**: The system needs to enforce state transitions (DRAFT → COMMITTED → APPROVED) across all developers

While Git serves as the ultimate source of truth for auditability and version control, we need a more dynamic synchronization mechanism for active development. The challenge is balancing:
- **Local autonomy**: Developers should work offline without constant network dependency
- **Real-time collaboration**: Changes should propagate quickly to prevent duplicate work
- **Conflict resolution**: The system should detect and help resolve conflicts intelligently
- **Git compatibility**: The workflow must integrate seamlessly with existing Git-based processes

## Decision

We will implement a **git-like distributed synchronization architecture** with the following components:

### 1. Three-Layer Architecture
```
┌─────────────────────────────────────────────────┐
│ Git Repository (.agent/cache/*.md)              │ ← Source of Truth
└─────────────────┬───────────────────────────────┘
                  │ export/import
┌─────────────────▼───────────────────────────────┐
│ Local SQLite (.agent/cache/agent.db)            │ ← Developer Workspace
└─────────────────┬───────────────────────────────┘
                  │ push/pull (sync)
┌─────────────────▼───────────────────────────────┐
│ Supabase PostgreSQL (Remote)                    │ ← Real-Time Sync
└─────────────────────────────────────────────────┘
```

### 2. Command Set (Inspired by Git)
- **`agent sync init`**: Initialize local database + configure remote
- **`agent sync push`**: Upload local changes to Supabase (with conflict detection)
- **`agent sync pull`**: Download remote changes from Supabase (with merge)
- **`agent sync status`**: Show local changes, remote changes, conflicts
- **`agent export`**: Export SQLite → Markdown (for Git commits)
- **`agent import-plan/story/runbook`**: Import Markdown → SQLite (from STDIN or file paths)

### 3. Synchronization Semantics
- **Push**: Fast-forward if no conflicts; otherwise, requires conflict resolution
- **Pull**: Three-way merge (local, remote, common ancestor) with automatic resolution where possible
- **Conflict Detection**: Version vectors or last-write-wins with conflict markers
- **Offline Mode**: All operations work locally; push/pull deferred until online

### 4. Data Flow
1. **New Artifact Creation**: `agent new-story` → SQLite → auto-push to Supabase
2. **Edit Workflow**: Edit locally → `agent sync push` (manual or automatic)
3. **Collaboration**: Other developers run `agent sync pull` to get updates
4. **Git Export**: Periodically run `agent export` → commit markdown to Git
5. **Fresh Clone**: `git clone` → `agent import-*` → initialize SQLite from markdown

## Alternatives Considered

### Option A: Pure Git-Based Workflow
**Description**: Continue using only Git for synchronization, with markdown files as the sole storage.

**Rejected because**:
- Too slow for real-time collaboration (commit/push/pull overhead)
- Poor conflict resolution for structured artifacts
- No enforcement of state transitions without server-side hooks
- Requires constant Git knowledge from developers

### Option B: Direct Supabase Integration (No Local Cache)
**Description**: Store all artifacts directly in Supabase; read/write over network for every operation.

**Rejected because**:
- Network dependency blocks all work when offline
- Higher latency for operations (100ms+ vs <10ms local)
- Violates "Git as source of truth" requirement
- Risk of data loss if Supabase unavailable

### Option C: CRDT-Based Sync (e.g., Yjs, Automerge)
**Description**: Use Conflict-free Replicated Data Types for automatic merge.

**Rejected because**:
- Over-engineered for structured artifacts (not free-form text)
- Complexity of CRDT implementation and debugging
- Harder to reason about merge semantics
- Integration with existing markdown/Git workflow unclear

### Option D: Centralized Server with REST API
**Description**: Build a custom API server for artifact management.

**Rejected because**:
- More infrastructure to maintain (vs. Supabase managed service)
- Doesn't leverage Supabase real-time features
- SQLite still needed for local caching
- Adds unnecessary abstraction layer

## Consequences

### Positive
1. **Developer Autonomy**: Work offline; push when ready (like Git)
2. **Real-Time Awareness**: `agent sync pull` shows what others are doing
3. **Fast Local Operations**: SQLite provides <100ms CRUD performance
4. **Familiar Mental Model**: Git users understand push/pull/status immediately
5. **Git Integration**: Export to markdown maintains auditability and version control
6. **Conflict Visibility**: System detects conflicts before they become Git merge issues
7. **Scalability**: SQLite + Supabase handle 1000+ artifacts efficiently
8. **State Enforcement**: Centralized Supabase can validate state transitions globally

### Negative
1. **Complexity**: Three-layer architecture (Git, SQLite, Supabase) requires careful state management
2. **Learning Curve**: Developers must understand when to use `sync`, `export`, `import`
3. **Data Consistency Risk**: Bugs in sync logic could cause divergence across layers
4. **Migration Cost**: Existing markdown workflows need migration to SQLite
5. **Partial Sync Issues**: If push/pull fails midway, system could be in inconsistent state
6. **Debugging Difficulty**: Troubleshooting sync issues requires understanding all three layers

## Supersedes
None (initial ADR for synchronization architecture)
