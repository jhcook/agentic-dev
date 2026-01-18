# INFRA-017: Integrate Anthropic Claude Provider

## State
COMMITTED

## Problem Statement
The agent framework currently supports three AI providers (GitHub CLI, Gemini, OpenAI), but lacks support for Anthropic Claude. Claude is a leading AI model known for excellent reasoning, coding assistance, and large context windows (200K tokens). Adding Claude as a provider would give users more flexibility in choosing their preferred AI backend and provide an additional fallback option for reliability.

## User Story
As a **developer using the agent CLI**, I want **to configure Anthropic Claude as an AI provider** so that **I can leverage Claude's capabilities for AI-assisted development workflows and have more provider options**.

## Acceptance Criteria
- [ ] **SDK Integration**: The `anthropic` Python SDK is added as a dependency in `pyproject.toml`.
- [ ] **Environment Variable**: System checks for `ANTHROPIC_API_KEY` environment variable during initialization.
- [ ] **Router Config**: Claude models are defined in `router.yaml` with appropriate tier, context window, and cost metadata.
- [ ] **Valid Providers**: `config.py` is updated to include `"anthropic"` in the list of valid providers.
- [ ] **Service Implementation**: `service.py` includes Anthropic client initialization and a handler in `_try_complete()`.
- [ ] **Fallback Chain**: Anthropic is added to the provider fallback chain for automatic failover.
- [ ] **Negative Test**: System handles missing `ANTHROPIC_API_KEY` gracefully without crashing.
- [ ] **Provider Selection**: User can explicitly select Anthropic via `--provider anthropic` flag.

## Non-Functional Requirements
- **Performance**: Claude API calls should use appropriate timeouts (120s minimum for large contexts).
- **Security**: API key must only be read from environment variables, never hardcoded.
- **Compliance**: No PII should be logged in AI request/response traces.
- **Observability**: Prometheus counter `ai_command_runs_total` should track Claude usage with `provider="anthropic"` label.

## Linked ADRs
- ADR-001 (if exists for AI provider architecture)

## Impact Analysis Summary
- **Components touched**: `service.py`, `config.py`, `router.yaml`, `pyproject.toml`
- **Workflows affected**: All AI-powered commands (`implement`, `impact`, `panel`, etc.)
- **Risks identified**: API rate limits, SDK version compatibility, cost management

## Test Strategy
- **Unit Tests**: Mock Anthropic client and verify `_try_complete()` handler returns expected content.
- **Integration Tests**: With valid API key, verify end-to-end completion via `agent impact` command.
- **Negative Tests**: Verify graceful handling when API key is missing or invalid.
- **Fallback Tests**: Verify provider chain switches from failing provider to Anthropic (and vice versa).

## Rollback Plan
- Revert changes to `service.py`, `config.py`, `router.yaml`, and `pyproject.toml`.
- Anthropic is an additive feature; removal has no impact on existing providers.
