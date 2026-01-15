# Supabase Integration & Sync Setup

The `agent sync` command allows you to synchronize your local agent state (Stories, Plans, Runbooks, ADRs) with a remote Supabase project. This enables distributed collaboration across different environments.

## 1. Prerequisites

Ensure you have the `supabase` Python package installed:

```bash
pip install supabase
# Or install the agent package in editable mode
pip install -e .agent
```

## 2. Supabase Project Setup

1.  **Create a Project**: Go to [supabase.com](https://supabase.com) and create a new project.
2.  **Database Schema**: You need to create the required tables (`artifacts`, `history`, `links`).
    *   Go to the **SQL Editor** in your Supabase Dashboard.
    *   Copy the content from `.agent/src/agent/db/supabase_schema.sql` in this repository.
    *   Run the SQL query to create the tables and set up Row Level Security (RLS) policies.

## 3. Configuration

### Project URL
Update `.agent/etc/sync.yaml` with your Supabase Project URL:

```yaml
supabase_url: "https://your-project-id.supabase.co"
supabase_table: "artifacts"
```

You can find this URL in **Settings > API** in the Supabase Dashboard.

## 4. Authentication (CRITICAL)

The agent requires **Service Role** access to bypass RLS for certain operations or to act as a privileged administrator of the artifact state.

> [!WARNING]
> Do **NOT** use the `anon` / `public` key. The agent sync functionality performs write operations that are restricted by RLS policies for standard users.

### How to get the Service Role Key:
1.  Go to **Settings > API** in your Supabase Dashboard.
2.  Look for the **Project API keys** section.
3.  Find the `service_role` (secret) key. **Do not expose this key in public client-side code.**

### Setting the Credential:

You must provide this key to the agent via the `SUPABASE_ACCESS_TOKEN` environment variable.

**Option A: Environment Variable (Recommended for CI/CD)**
```bash
export SUPABASE_ACCESS_TOKEN="eyJh..."
```

**Option B: Local Secret File (Recommended for Dev)**
Create a file at `.agent/secrets/supabase_access_token`.
```bash
mkdir -p .agent/secrets
echo "eyJh..." > .agent/secrets/supabase_access_token
```
*Note: `.agent/secrets/` is git-ignored by default.*

## 5. Usage

Once configured, you can use the sync commands:

*   **Push**: `agent sync push` (Local -> Remote)
*   **Pull**: `agent sync pull` (Remote -> Local)
*   **Status**: `agent sync status` (Local Check)
