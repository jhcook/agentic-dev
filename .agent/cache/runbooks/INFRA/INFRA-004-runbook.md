# INFRA-004: Distributed Cache Synchronization with SQLite and Supabase

Status: ACCEPTED

## Goal Description
The objective of this story is to implement a git-like distributed cache synchronization system to enable remote developers working with the `agent` CLI to collaboratively modify artifacts (Plans, Stories, Runbooks) in real-time without file collisions, while retaining Git as the single source of truth. The solution includes a local SQLite database and Supabase as a remote synchronization layer for seamless and responsive artifact management.

---

## Panel Review Findings

### **@Architect**
1. Alignment with ADR Standards: The proposed architecture complies with ADR-001 through ADR-003, adhering to the immutability of decision logic.
2. Issue of Schema Drift: Synchronization between SQLite and Supabase may introduce schema drift. A well-defined and versioned schema evolution process must be implemented.
3. Scalability Risks: The 1000 artifact constraint is acceptable for current use but mitigation for scalability (e.g., database sharding or caching in Supabase) should be considered.
4. Workflow Management: Explicit lock/version-check mechanisms are critical to avoid race conditions, especially during the `push`/`pull` process.

### **@Security**
1. API Key Management: Proper storage of Supabase API keys is crucial—use environment variables and prohibit hardcoding values in the config file (`sync.yaml`).
2. Data Security: Ensure Supabase row-level security (RLS) policies correctly isolate developer artifacts.
3. PII Scrubbing: Implement mechanisms to sanitize PII from synchronized data.
4. Conflict Resolution: Data integrity during conflict resolution must be maintained to prevent intentional or unintentional data corruption.

### **@QA**
1. Test Coverage:
   - Unit Tests: CRUD operations in SQLite and data consistency validation.
   - Integration Tests: End-to-end Supabase interactions.
   - Performance Tests: High-load scenarios (1000+ records) and concurrent sync operations.
2. Conflict Resolution Testing: Simulate edge cases for manual vs automatic conflict resolution workflows.
3. Offline Testing: Evaluate the system's ability to queue operations and recover from failed synchronization attempts.

### **@Docs**
1. Documentation Updates:
   - Add detailed configuration guidelines to `README.md` for `.agent/etc/sync.yaml`.
   - Update usage documentation to include new commands such as `agent sync push/pull/status/init`.
   - Provide an example of the conflict resolution process in documentation.
2. API Contract: All changes to the REST API with Supabase must be documented in the OpenAPI spec, per governance rules.

### **@Compliance**
1. Logging Standards: Ensure detailed audit logs for every sync operation, including developer identity, timestamp, and list of changes.
2. GDPR Compliance: Include functionality to delete all records associated with a developer upon request.
3. OpenAPI Schema Compliance: Verify Supabase endpoints comply with the current OpenAPI specification to avoid unapproved changes.

### **@Observability**
1. Structured Logs: All sync operations, including errors, should be logged with sufficient metadata (e.g., user, artifact ID, operation type).
2. Metrics Collection:
   - Sync duration, artifact count, conflict resolution statistics, error rate.
3. Distributed Tracing: Utilize OpenTelemetry for debugging issues in Supabase sync interactions.

---

## Implementation Steps

### SQLite Database Initialization
#### [NEW] `.agent/src/agent/db/init.py`
1. Implement SQLite schema based on artifact and history data models.
2. Create a migration strategy for schema evolution versioning.

#### [NEW] `.agent/src/agent/db/schema.sql`
- Define the schema:
  - `artifacts` table with fields: `id`, `type`, `content`, `last_modified`, `version`, `state`, `author`.
  - `history` table with fields: `artifact_id`, `change_id`, `timestamp`, `author`, `description`, `delta`.
3. Include migration scripts to handle schema updates.

#### [NEW] `.agent/src/agent/db/supabase_schema.sql`
- Reference SQL file for setting up the Supabase remote:
  - Table definitions matching SQLite schema.
  - RLS policies for developer access control.

### Synchronization Commands
#### [NEW] `.agent/src/agent/sync/sync.py`
- Implement core functionalities for `sync push`, `sync pull`, `sync status`:
  1. `push`:
     - Serialize local changes from SQLite.
     - Send changes to Supabase via API, maintain versioning to identify conflicts.
     - Implement automated conflict resolution; prompt user for manual input if necessary.
  2. `pull`:
     - Retrieve artifacts from Supabase.
     - Merge changes into SQLite; preserve Git's status fields (e.g., `Status: APPROVED`).
  3. `status`:
     - Compare local and remote data for modified or conflicting artifacts.

### Configuration Management
#### [NEW] `.agent/etc/sync.yaml`
- Add configuration fields:
  - `supabase_url`
  - `supabase_table`
- **Security Note**: `supabase_api_key` MUST be loaded from the `SUPABASE_SERVICE_ROLE_KEY` environment variable. Do NOT store it in `sync.yaml`.
- Provide examples of configuration with detailed comments.

### Conflict Resolution Workflow
#### [NEW] `.agent/src/agent/sync/conflict.py`
1. Implement conflict detection:
   - Detect overlapping updates to artifact versions.
2. Allow user resolution via CLI:
   - Show clear conflict markers and both versions side-by-side.
   - Prompt user to select or merge changes using standard editors.

### CLI Command Additions
#### [MODIFY] `.agent/src/agent/commands/`
- Add `sync` commands (`init`, `push`, `pull`, `status`, `export`, `import`).
- Modify `new-plan`, `new-story`, and `new-runbook` to include SQLite auto-sync functionalities.

### Observability
#### [NEW] `.agent/src/agent/logging.py`
1. Implement structured logging for operations (e.g., `sync push`, `pull`, version conflicts).
2. Integrate OpenTelemetry for tracing distributed sync activities.

---

## Verification Plan

### Automated Tests
- [ ] Unit Tests:
  - CRUD operations in SQLite.
  - Validation of version tracking and conflict detection.
- [ ] Integration Tests:
  - Full Supabase synchronization cycle (push, pull scenarios).
  - Simulate race conditions with multiple threads and ensure consistent results.
- [ ] Performance Tests:
  - Measure sync performance with 1000 concurrent artifacts.
  - Test offline mode with queued operations and reconnect handling.

### Manual Verification
- [ ] Verify developer workflows:
  - Create artifact, push to remote, pull changes to another developer's local database.
  - Resolve conflicts with CLI tools.
- [ ] Execute rollback scenarios:
  - Migrate back to a fully markdown-based workflow.

---

## Definition of Done

### Documentation
- [ ] CHANGELOG.md updated with changes.
- [ ] docs/ updated with sync guidelines.
- [ ] OpenAPI documentation updated for any Supabase-related API changes.
- [ ] Clear conflict resolution workflows documented.

### Observability
- [ ] Logging mechanism for all updates and sync operations.
- [ ] Metrics for latency, artifact count, performance, and errors.
- [ ] Distributed tracing implemented for supabase-related interactions.

### Testing
- [ ] Unit tests for defined SQLite and syncing use cases.
- [ ] Integration tests for offline mode, multiple developers.
- [ ] Performance metrics validated (<100ms for SQLite operations under load).
- [ ] Security tests for API keys and access controls passed.