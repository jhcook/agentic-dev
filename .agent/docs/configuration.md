# Configuration

## Configuration Files

### `.agent/etc/agents.yaml`
Defines the persona and responsibilities of each AI agent.

### `.agent/etc/router.yaml`
Configures how the router directs tasks to specific agents.

## Secrets

We use `.env` for local secrets and `.agent/secrets/` for file-based secrets.

- **GEMINI_API_KEY**: Required for AI.
- **SUPABASE_ACCESS_TOKEN**: Required for Synchronization. See [Supabase Integration](supabase_integration.md).
