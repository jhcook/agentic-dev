# INFRA-185: Add Claude Provider with ~/.claude/settings.json and AWS Bedrock Support

## State

COMMITTED

## Problem Statement

The agent framework currently supports Anthropic Claude via the `anthropic` provider (direct API
key) and `vertex-anthropic` (Claude on Vertex AI via ADC). However, many developers using Claude
Code already have a fully configured `~/.claude/settings.json` that specifies AWS Bedrock
credentials, region, profile, and model preferences. There is no way to leverage this existing
configuration — users who want to route the agent's LLM calls through Bedrock must manually set
environment variables and use the generic `anthropic` provider, which doesn't understand the
Bedrock transport.

The `~/.claude/settings.json` file is the standard Claude Code configuration surface and looks
like this:

```json
{
  "env": {
    "CLAUDE_CODE_USE_BEDROCK": "1",
    "AWS_REGION": "us-east-1",
    "AWS_PROFILE": "my-aws-profile",
    "ANTHROPIC_MODEL": "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
  },
  "awsAuthRefresh": "aws sso login --profile my-aws-profile"
}
```

The Anthropic Python SDK already ships `AnthropicBedrock` (via the `anthropic[bedrock]` extra)
which constructs a Bedrock-native client using standard AWS credential chains. Adding a `claude`
provider that reads the settings file and selects the appropriate SDK client (Bedrock vs direct
API) should be straightforward.

## User Story

As a **Platform Developer with an existing `~/.claude/settings.json`**, I want **the agent to
auto-detect and use my Bedrock configuration** so that **I can use `agent provider claude`
without manually exporting AWS environment variables or managing a separate API key.**

## Acceptance Criteria

- [ ] **AC-1**: New `claude` provider module at `agent/core/ai/providers/claude.py` implements
      `BaseProvider` with `generate()` and `stream()` methods using the Anthropic Messages API.
- [ ] **AC-2**: Settings loader reads `~/.claude/settings.json`, parses the `env` block, and
      injects values into `os.environ` (without overwriting existing env vars).
- [ ] **AC-3**: When `CLAUDE_CODE_USE_BEDROCK=1` is detected (from settings or env), the provider
      builds an `AnthropicBedrock` client with `aws_region` and optional `aws_profile`.
- [ ] **AC-4**: When Bedrock is NOT enabled, the provider falls back to the standard `Anthropic`
      client using `ANTHROPIC_API_KEY` (from env or secret manager).
- [ ] **AC-5**: The `awsAuthRefresh` command (if present in settings) is executed before client
      construction to refresh SSO credentials automatically.
- [ ] **AC-6**: The `claude` provider is registered in the provider factory
      (`providers/__init__.py`), service PROVIDERS dict, model defaults, fallback chain, and
      `get_valid_providers()`.
- [ ] **AC-7**: `router.yaml` includes Bedrock model entries under `provider: "claude"` and
      `provider_priority` includes `"claude"`.
- [ ] **AC-8**: `agent.yaml` model config includes a `claude` entry.
- [ ] **AC-9**: `pyproject.toml` dependency updated from `anthropic>=0.3.0` to
      `anthropic[bedrock]>=0.3.0`.
- [ ] **AC-10**: The `claude` prefix (`claude-*`) resolves to `ClaudeProvider` in the prefix
      fallback map.
- [ ] **Negative Test**: If neither `CLAUDE_CODE_USE_BEDROCK=1` nor `ANTHROPIC_API_KEY` is set
      and no `~/.claude/settings.json` exists, the provider raises `AIConfigurationError` with
      a helpful message.
- [ ] **AC-11**: Pipeline hardening — `runbook_postprocess.py` removes empty MODIFY blocks
      and `parser.py` filters malformed blocks before Pydantic validation, preventing
      `agent implement` schema crashes on AI-generated runbooks with empty content.

## Non-Functional Requirements

- **Performance**: Settings file is loaded once on provider init, not per-request.
- **Security**: AWS credentials are never logged. `_apply_settings_env` only sets env vars
  that are NOT already present (explicit env always wins).
- **Compliance**: No secrets stored in the provider module; all credential resolution uses
  the standard AWS credential chain or the existing secret manager.
- **Observability**: Provider logs `claude: building AnthropicBedrock client` or
  `claude: building standard Anthropic client` at INFO level on init.

## Linked ADRs

- ADR-046: Structured Logging & Observability

## Linked Journeys

- JRN-020: Integrate Anthropic Claude Provider

## Impact Analysis Summary

Components touched:
- `agent/core/ai/providers/claude.py` — NEW: ClaudeProvider + settings loader + client builder
- `agent/core/ai/providers/__init__.py` — Register `claude` in provider map + prefix fallback
- `agent/core/ai/service.py` — PROVIDERS dict, model defaults, reload() init, fallback chain,
  stream/complete dispatch branches, host_map for SSL diagnostics
- `agent/core/config.py` — `get_valid_providers()`, `get_provider_config()`,
  `_get_enabled_providers()` additions
- `.agent/etc/router.yaml` — Bedrock model entries + provider_priority update
- `.agent/etc/agent.yaml` — claude model entry
- `.agent/pyproject.toml` — `anthropic[bedrock]` dependency
- `.agent/docs/architecture/claude-provider-design.md` — NEW: architecture review document
- `.agent/docs/providers/claude.md` — NEW: user-facing provider documentation
- `.agent/src/agent/utils/rollback_infra_185.py` — NEW: rollback utility script
- `.agent/tests/agent/core/ai/providers/test_claude_provider.py` — NEW: unit tests
- `.agent/src/agent/commands/runbook_postprocess.py` — FIX: systemic empty MODIFY block removal
- `.agent/src/agent/core/implement/parser.py` — FIX: malformed block filtering in schema validator
- `.agent/CHANGELOG.md` — INFRA-185 entry

Workflows affected:
- `agent provider claude` — new provider selection
- Smart Router — will now route to `claude` when configured and prioritised
- `agent implement` — now resilient to empty MODIFY blocks (systemic pipeline fix)

Risks identified:
- `anthropic[bedrock]` pulls in `botocore`/`boto3` which adds ~50MB of dependencies. This is
  acceptable since Bedrock users already have the AWS CLI/SDK installed.
- `awsAuthRefresh` runs a shell command — bounded by 60s timeout and logged; failure is non-fatal.

## Test Strategy

- **Unit** (`test_claude_provider.py`): `load_claude_settings()` parses valid JSON, returns
  empty dict on missing file, handles malformed JSON.
- **Unit**: `_apply_settings_env()` injects env vars only when not already present.
- **Unit**: `ClaudeProvider.__init__()` returns `AnthropicBedrock` client when Bedrock enabled,
  `Anthropic` client when API key present, raises `AIConfigurationError` when neither is available.
- **Unit**: `_run_aws_auth_refresh()` executes the refresh command via `shlex.split` (no shell),
  handles timeouts and missing binaries gracefully.
- **Unit**: `ClaudeProvider.generate()` delegates to the Anthropic Messages API and returns text.
- **Unit**: `ClaudeProvider.stream()` delegates to the Anthropic Messages streaming API and
  yields text chunks.
- **Exception Strategy**: SDK exceptions (`anthropic.APIError`) are re-raised directly to the
  caller. This is intentional — the provider does not map to typed errors; the service layer
  handles error classification.
- **Unit** (`test_pipeline_hardening_infra_185.py`): AC-11 pipeline hardening coverage:
  - `_autocorrect_schema_violations()` removes empty MODIFY blocks (no `<<<SEARCH`) and
    replaces them with a traceability comment. Valid MODIFY blocks with S/R content are preserved.
  - `validate_runbook_schema()` reports malformed MODIFY blocks (no S/R content) and malformed
    NEW blocks (no code content) as violations, filtering them before Pydantic validation to
    prevent schema crashes.
- **Integration** (deferred): Provider factory `get_provider("claude")` returns `ClaudeProvider`
  and prefix fallback `get_provider("claude-haiku")` resolves correctly.

## Rollback Plan

All changes are additive. Removing the `claude.py` module and reverting the registry entries
restores the previous state with zero side effects. The `anthropic[bedrock]` extra is
backwards-compatible — existing `anthropic` imports continue to work.

## Copyright

Copyright 2026 Justin Cook
