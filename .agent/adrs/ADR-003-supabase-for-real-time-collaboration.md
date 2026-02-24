# ADR-003: Supabase for Real-Time Collaboration

## Status
Proposed

## Context
As defined in ADR-001, the distributed synchronization architecture requires a remote database for real-time collaboration among multiple developers. This remote layer must support:

1. **Multi-Developer Sync**: Multiple developers push/pull artifacts concurrently
2. **Conflict Detection**: Identify when two developers modify the same artifact
3. **Access Control**: Ensure developers only access artifacts they're authorized to see
4. **Real-Time Updates**: Optional live notifications when artifacts change
5. **Scalability**: Handle teams of 10-100 developers with 1000+ artifacts
6. **Auditability**: Track who changed what and when
7. **Low Latency**: Push/pull operations complete in <2 seconds (global)
8. **Managed Service**: Minimal operational overhead (no self-hosted infrastructure)
9. **Cost-Effective**: Free tier for small teams, affordable for larger teams
10. **Developer-Friendly**: Simple API, good Python SDK

The service must integrate seamlessly with the local SQLite layer (ADR-002) and support the git-like sync workflow (ADR-001).

## Decision

We will use **Supabase** (managed PostgreSQL with real-time features) as the remote collaboration layer.

### Architecture

```
┌───────────────────────────────────────────────────┐
│ Developer Machines                                 │
│  ┌─────────────────────────────────────────────┐  │
│  │ .agent/cache/agent.db (SQLite)              │  │
│  │  ↓ agent sync push (Python client)          │  │
│  └──────────────────┬──────────────────────────┘  │
└───────────────────────┼───────────────────────────┘
                        │ HTTPS (Supabase Python SDK)
                        ▼
┌───────────────────────────────────────────────────┐
│ Supabase (Managed PostgreSQL + Real-Time)         │
│  ┌─────────────────────────────────────────────┐  │
│  │ PostgreSQL Database                         │  │
│  │  - artifacts table (mirrors SQLite schema)  │  │
│  │  - artifact_history table                   │  │
│  │  - Row-Level Security (RLS) policies        │  │
│  └─────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────┐  │
│  │ Real-Time Server (WebSocket)                │  │
│  │  - Broadcasts INSERT/UPDATE/DELETE events   │  │
│  └─────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────┘
```

### Schema (PostgreSQL)
Mirrors the SQLite schema from ADR-002, with additions for multi-tenancy:

```sql
-- Core artifacts table (same as SQLite, plus team_id)
CREATE TABLE artifacts (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    state TEXT,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    author TEXT NOT NULL,               -- User who created/updated
    team_id UUID NOT NULL,              -- Multi-tenant: isolate by team
    remote_version INTEGER DEFAULT 0,
    is_dirty BOOLEAN DEFAULT FALSE
);

-- Version history (same as SQLite)
CREATE TABLE artifact_history (
    id SERIAL PRIMARY KEY,
    artifact_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    author TEXT NOT NULL,
    team_id UUID NOT NULL,
    FOREIGN KEY (artifact_id) REFERENCES artifacts(id)
);

-- Row-Level Security: Developers only see their team's artifacts
ALTER TABLE artifacts ENABLE ROW LEVEL SECURITY;
CREATE POLICY artifacts_team_isolation ON artifacts
    FOR ALL
    USING (team_id = auth.jwt() ->> 'team_id');

ALTER TABLE artifact_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY history_team_isolation ON artifact_history
    FOR ALL
    USING (team_id = auth.jwt() ->> 'team_id');

-- Indexes
CREATE INDEX idx_artifacts_team_type ON artifacts(team_id, type);
CREATE INDEX idx_artifacts_team_state ON artifacts(team_id, state);
```

### Configuration (`.agent/etc/sync.yaml`)

```yaml
remote:
  type: supabase
  url: https://xyzcompany.supabase.co
  anon_key: ${SUPABASE_ANON_KEY}  # Public API key (read from env)
  service_role_key: ${SUPABASE_SERVICE_KEY}  # Admin key (optional)
  team_id: ${SUPABASE_TEAM_ID}  # Or inferred from JWT

sync:
  auto_push: true  # Auto-push after `agent new-story`, etc.
  auto_pull_interval: 300  # Seconds (0 = disabled)
  conflict_strategy: manual  # "manual", "local_wins", "remote_wins"
```

### Python Client (Supabase SDK)

```python
from supabase import create_client, Client

class RemoteSync:
    def __init__(self):
        self.client: Client = create_client(
            supabase_url=config.remote.url,
            supabase_key=config.remote.anon_key
        )
    
    def push_artifact(self, artifact: Artifact):
        """Upload local artifact to Supabase."""
        data = {
            "id": artifact.id,
            "type": artifact.type,
            "title": artifact.title,
            "content": artifact.content,
            "version": artifact.version,
            "author": artifact.author,
            "team_id": config.remote.team_id,
        }
        
        # Upsert with conflict detection
        response = self.client.table("artifacts").upsert(data).execute()
        
        if response.data[0]["version"] != artifact.version:
            raise ConflictError("Remote version changed; pull first")
    
    def pull_artifacts(self, since: datetime) -> List[Artifact]:
        """Download remote artifacts updated since timestamp."""
        response = self.client.table("artifacts") \
            .select("*") \
            .gte("updated_at", since.isoformat()) \
            .execute()
        
        return [Artifact.from_dict(row) for row in response.data]
```

### Real-Time Subscriptions (Optional)
For live collaboration, developers can subscribe to changes:

```python
def on_artifact_change(payload):
    """Handle real-time update from Supabase."""
    print(f"Artifact {payload['new']['id']} updated by {payload['new']['author']}")
    # Optionally: auto-pull and notify user

supabase.table("artifacts").on("UPDATE", on_artifact_change).subscribe()
```

## Alternatives Considered

### Option A: Self-Hosted PostgreSQL
**Description**: Deploy own PostgreSQL instance on AWS/GCP/Azure.

**Rejected because**:
- Requires infrastructure management (backups, scaling, security patches)
- No built-in real-time features (would need custom WebSocket server)
- Higher operational cost (DevOps time + hosting fees)
- Slower time-to-market (setup, hardening, monitoring)

### Option B: Firebase Realtime Database / Firestore
**Description**: Use Google's Firebase for real-time sync.

**Rejected because**:
- NoSQL data model less suitable for structured artifacts
- Limited complex querying (no SQL joins, aggregations)
- Pricing model unpredictable for read-heavy workloads
- Python SDK less mature than JavaScript SDK

### Option C: CouchDB / PouchDB (Offline-First Sync)
**Description**: Use CouchDB's built-in replication protocol.

**Rejected because**:
- Conflict resolution model (revision trees) more complex than needed
- Requires self-hosting or Cloudant (IBM Cloud, deprecated)
- Python support less robust than PostgreSQL
- Overkill for structured artifacts (designed for document-oriented use cases)

### Option D: AWS DynamoDB with AppSync
**Description**: Use DynamoDB for storage + AppSync for real-time GraphQL.

**Rejected because**:
- More complex setup (multiple AWS services)
- GraphQL adds unnecessary abstraction layer
- Higher cost than Supabase free tier
- Vendor lock-in to AWS ecosystem

### Option E: Custom REST API with Django/FastAPI
**Description**: Build a custom API server with Django or FastAPI.

**Rejected because**:
- Requires building/maintaining authentication, authorization, real-time, etc.
- Significant development time (weeks vs hours for Supabase)
- Self-hosting or managed hosting adds operational burden
- Reinvents features Supabase provides out-of-the-box

## Consequences

### Positive
1. **Zero Infrastructure**: Managed service; no servers to maintain
2. **Real-Time Built-In**: WebSocket subscriptions for live updates (optional)
3. **Row-Level Security**: Built-in multi-tenancy via RLS policies
4. **PostgreSQL Power**: Full SQL capabilities (joins, aggregations, transactions)
5. **Generous Free Tier**: 500MB database, 2GB file storage, 50,000 monthly active users
6. **Auto-Scaling**: Supabase handles traffic spikes automatically
7. **Mature Python SDK**: Official `supabase-py` library with good documentation
8. **Dashboard for Debugging**: Web UI to inspect database, logs, and API usage
9. **Migration Path**: If needed, can export PostgreSQL and self-host
10. **Authentication Ready**: Supabase Auth integrates seamlessly (future: SSO, GitHub login)

### Negative
1. **Vendor Lock-In**: Depends on Supabase infrastructure (mitigated: PostgreSQL is portable)
2. **Cost at Scale**: Paid tier required beyond free tier limits (~$25/month for Pro)
3. **Network Dependency**: Push/pull requires internet (mitigated: offline-first design in ADR-001)
4. **Latency**: Remote calls slower than local SQLite (~100ms-1s vs <10ms)
5. **Learning Curve**: Developers must understand RLS policies, JWT authentication
6. **Schema Synchronization**: Migrations must apply to both SQLite and Supabase
7. **Rate Limits**: Supabase API has rate limits (1000 req/min on free tier)
8. **Data Residency**: Supabase hosts in specific regions (compliance consideration for GDPR)
9. **Offline mode limitations:** Real-time collaboration relies on Supabase's cloud infrastructure, meaning offline capabilities will be restricted to local caching until reconnected.
10. **Security:** Database access policies (RLS) must be carefully designed to prevent unauthorized story modifications.

## Copyright

Copyright 2026 Justin Cook

## Implementation Notes

### Setup Instructions
1. **Create Supabase Project**: Sign up at <https://supabase.com>, create project
2. **Run Migrations**: Apply schema SQL to Supabase SQL Editor
3. **Configure RLS**: Enable Row-Level Security and create policies
4. **Generate Team ID**: Create team UUID, set in `.agent/etc/sync.yaml`
5. **Distribute Keys**: Share `SUPABASE_ANON_KEY` and `SUPABASE_TEAM_ID` with team

### Security Considerations
- **Anon Key**: Public-safe key (enforced by RLS policies)
- **Service Role Key**: Admin key (full access; keep secret, use only for migrations)
- **JWT Authentication**: Future enhancement for per-user auth (currently team-based)
- **HTTPS Only**: All traffic encrypted in transit
- **Environment Variables**: Store keys in `.env` or CI/CD secrets, never in Git

### Monitoring & Observability
- **Supabase Dashboard**: Track API usage, query performance, error logs
- **Logging**: Log all push/pull operations locally (`.agent/logs/sync.log`)
- **Metrics**: Track sync latency, conflict rate, pull frequency

### Cost Estimation
- **Free Tier**: 500MB database (sufficient for ~10,000 artifacts), unlimited API requests
- **Pro Tier ($25/month)**: 8GB database, 100GB bandwidth, point-in-time recovery
- **Team Tier ($599/month)**: Dedicated infrastructure, SOC2 compliance

## Supersedes
None (initial ADR for remote collaboration)
