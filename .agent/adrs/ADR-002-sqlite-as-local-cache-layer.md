# ADR-002: SQLite as Local Cache Layer

## Status
Proposed

## Context
As defined in ADR-001, the distributed synchronization architecture requires a local database layer between the markdown files (Git) and the remote database (Supabase). This local layer must support:

1. **Fast CRUD Operations**: Read/write artifacts in <100ms for responsive CLI experience
2. **Offline Capability**: Full functionality without network access
3. **Structured Queries**: Filter stories by state, search plans by title, etc.
4. **ACID Transactions**: Ensure data integrity during concurrent operations
5. **Schema Management**: Support migrations as artifact structure evolves
6. **Lightweight**: No separate server process or complex setup
7. **Python Integration**: First-class support for the `agent` CLI (Python-based)
8. **Version Tracking**: Store artifact history, timestamps, and author information
9. **Conflict Detection**: Enable three-way merge by tracking base versions

The database must be **developer-friendly** (zero-config, just works) and **migration-friendly** (easy to export/import to markdown).

## Decision

We will use **SQLite** as the local cache layer, stored at `.agent/cache/agent.db`.

### Schema Design
```sql
-- Core artifacts table (polymorphic: Plans, Stories, Runbooks)
CREATE TABLE artifacts (
    id TEXT PRIMARY KEY,              -- e.g., "INFRA-004", "ADR-001"
    type TEXT NOT NULL,               -- "plan", "story", "runbook", "adr"
    title TEXT NOT NULL,
    content TEXT NOT NULL,            -- Full markdown content
    state TEXT,                       -- "DRAFT", "COMMITTED", "APPROVED"
    version INTEGER DEFAULT 1,        -- Incremented on each update
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    author TEXT,                      -- Git user.name or SUPABASE_USER
    remote_version INTEGER DEFAULT 0, -- Last known remote version (for conflict detection)
    is_dirty BOOLEAN DEFAULT 0        -- Has local changes not pushed
);

-- Version history for conflict resolution and audit
CREATE TABLE artifact_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    author TEXT,
    FOREIGN KEY (artifact_id) REFERENCES artifacts(id)
);

-- Sync metadata
CREATE TABLE sync_state (
    key TEXT PRIMARY KEY,
    value TEXT
);  -- Stores: last_pull_timestamp, remote_url, etc.

-- Indexes for common queries
CREATE INDEX idx_artifacts_type ON artifacts(type);
CREATE INDEX idx_artifacts_state ON artifacts(state);
CREATE INDEX idx_artifacts_dirty ON artifacts(is_dirty);
CREATE INDEX idx_history_artifact ON artifact_history(artifact_id);
```

### ORM/Query Layer
Use **SQLAlchemy** (Python ORM) or raw **sqlite3** for simplicity:
- **SQLAlchemy Core**: Type-safe queries, schema migrations via Alembic
- **Raw sqlite3**: Zero dependencies, but more manual work

**Decision**: Start with **raw sqlite3** for simplicity; migrate to SQLAlchemy if complexity grows.

### Migration Strategy
- Use **`.agent/src/agent/db/migrations/`** directory with versioned SQL scripts
- On CLI startup, check schema version in `sync_state` table
- Auto-apply pending migrations (idempotent `CREATE TABLE IF NOT EXISTS`, `ALTER TABLE`)

### Concurrency Handling
- **WAL mode** (Write-Ahead Logging): Allows concurrent reads during writes
- **5-second timeout** on locks (fail gracefully if another process holds lock)
- **Row-level locking**: Use transactions appropriately to minimize contention

```python
# Example: Enable WAL mode on connection
conn = sqlite3.connect(".agent/cache/agent.db")
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=5000")
```

## Alternatives Considered

### Option A: Plain Markdown Files (Status Quo)
**Description**: Continue using markdown files as the only storage, parsed on-the-fly.

**Rejected because**:
- No structured queries (must parse every file to filter by state)
- No version tracking (would need custom metadata in frontmatter)
- Slow for large repos (1000+ files = 1000+ file reads)
- Difficult to implement conflict detection and merge

### Option B: PostgreSQL Client-Side
**Description**: Run a local PostgreSQL instance on each developer machine.

**Rejected because**:
- Requires separate server process (complex setup)
- Heavier resource usage (~50MB memory vs SQLite's ~1MB)
- Overkill for local-only operations
- PostgreSQL installation not guaranteed on developer machines

### Option C: Embedded Key-Value Store (e.g., LevelDB, RocksDB)
**Description**: Use a key-value store for artifact storage.

**Rejected because**:
- No SQL queries (must implement filtering/indexing manually)
- Less mature Python bindings than SQLite
- Overkill for structured data (artifacts are not blob storage)
- Harder to inspect/debug (no standard SQL tools)

### Option D: In-Memory Data Structures (Pickled Dicts)
**Description**: Load all artifacts into Python dicts, serialize to disk via pickle.

**Rejected because**:
- Entire dataset must fit in memory (scalability issue)
- No atomic updates (risk of data corruption on crash)
- No concurrent access support
- Slow for large datasets (deserialize everything on startup)

### Option E: TinyDB or SQLAlchemy with JSON Backend
**Description**: Use a document-oriented database like TinyDB.

**Rejected because**:
- No ACID guarantees (TinyDB uses JSON file locks)
- Slower than SQLite for queries
- Less tooling/ecosystem support
- SQLite already handles JSON via JSON1 extension

## Consequences

### Positive
1. **Zero Configuration**: SQLite is included in Python standard library; no setup required
2. **Fast Performance**: Sub-millisecond queries for typical workloads (<1000 artifacts)
3. **Offline-First**: No network dependency; all operations work locally
4. **ACID Compliance**: Data integrity guaranteed even if process crashes
5. **Mature Tooling**: Standard SQL tools (DB Browser, sqlite3 CLI) for debugging
6. **Cross-Platform**: Works identically on macOS, Linux, Windows
7. **Small Footprint**: Entire database typically <5MB for 1000 artifacts
8. **Schema Evolution**: SQL migrations well-understood and tooling-supported
9. **Developer Familiarity**: Most developers know SQL
10. **Version Control Friendly**: Single file (`.agent/cache/agent.db`) easy to backup/restore

### Negative
1. **Single File Locking**: Concurrent writes can contend (mitigated by WAL mode)
2. **No Built-In Replication**: Sync logic must be implemented manually (see ADR-001)
3. **Schema Rigidity**: Schema changes require migrations (vs schemaless NoSQL)
4. **Binary Format**: Harder to inspect than plain text (but `.agent export` mitigates this)
5. **Learning Curve**: Developers unfamiliar with SQL may struggle with queries
6. **Conflict Risk**: If `.agent/cache/agent.db` committed to Git by mistake, causes merge issues
   - **Mitigation**: Add `agent.db` to `.gitignore`

## Implementation Notes

### Bootstrapping
On first use (`agent sync init` or `agent new-story`), automatically:
1. Create `.agent/cache/agent.db` if not exists
2. Run schema initialization migrations
3. Import existing markdown files to SQLite (if any)

### Export/Import Commands
- **`agent export`**: Dump SQLite → Markdown (for Git commits)
  ```bash
  agent export  # Writes all artifacts to .agent/cache/*.md
  ```
- **`agent import-plan <path>`**: Parse markdown → SQLite
  ```bash
  agent import-plan .agent/cache/plans/INFRA/*.md
  ```

### Debugging
Use standard SQLite tools:
```bash
sqlite3 .agent/cache/agent.db "SELECT id, title, state FROM artifacts WHERE type='story';"
```

## Supersedes
None (initial ADR for local storage)
