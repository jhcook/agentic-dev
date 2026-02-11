# ADR-026: Service-Scoped Secret Management

## State

ACCEPTED

## Context

The `SecretManager` stores encrypted credentials in `.agent/secrets/` as JSON files named by **service** (e.g. `notion.json`, `openai.json`, `supabase.json`). The `get_secret(key, service=...)` API loads the corresponding file and decrypts the requested key.

A bug was discovered where `get_secret("token", service="agent")` was used for the Notion API token. This looked in `agent.json` (which contains `notion_page_id`, not the API token) instead of `notion.json` (which contains the encrypted token). The fix was to use `service="notion"`.

The `SERVICE_ENV_MAPPINGS` dictionary provides environment-variable fallbacks per service, enabling `NOTION_TOKEN` to be resolved when the encrypted secret is unavailable (e.g. CI environments).

## Decision

We adopt the **one-service-per-file** convention:

1. **Each external integration gets its own secrets file**: `notion.json`, `openai.json`, `gemini.json`, `anthropic.json`, `supabase.json`, `gh.json`.
2. **`get_secret()` calls must use the correct service name** matching the filename (without `.json`).
3. **`SERVICE_ENV_MAPPINGS`** must include a fallback entry for every service that has an environment-variable equivalent.
4. **The `agent.json` file** is reserved for agent-internal configuration secrets (e.g. `notion_page_id`, internal keys), **not** for third-party API tokens.

### Naming Convention

| Service File | Service Name | Keys | Env Fallback |
|---|---|---|---|
| `notion.json` | `notion` | `token` | `NOTION_TOKEN` |
| `openai.json` | `openai` | `api_key` | `OPENAI_API_KEY` |
| `gemini.json` | `gemini` | `api_key` | `GEMINI_API_KEY` |
| `anthropic.json` | `anthropic` | `api_key` | `ANTHROPIC_API_KEY` |
| `supabase.json` | `supabase` | `service_role_key`, `anon_key`, `url` | `SUPABASE_*` |
| `gh.json` | `gh` | `api_key` | `GH_API_KEY`, `GITHUB_TOKEN` |

## Alternatives Considered

- **Single `agent.json` for all secrets**: Rejected — mixing third-party tokens with internal config causes lookup ambiguity and the exact bug we fixed.
- **Environment variables only**: Rejected — encrypted at-rest storage is required for SOC 2 compliance (see ADR-018).

## Consequences

- **Positive**: Clear, unambiguous secret resolution — service name maps directly to filename.
- **Positive**: Environment-variable fallback enables CI/CD without encrypted secrets.
- **Negative**: Adding a new integration requires both a secrets file and a `SERVICE_ENV_MAPPINGS` entry. (Mitigated by the `agent onboard` wizard.)
