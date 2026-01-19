# INFRA-024: Agent List Models Command

## State
COMMITTED

## Problem Statement
Users struggle to know which AI models are actually available to use with the agent. This depends on their API key, the provider configuration, and dynamic availability (e.g., deprecated models). Debugging "404 Model Not Found" errors requires manual API calls or scripts.

## User Story
As a developer, I want to use `agent list-models <provider>` so that I can immediately see which models are available for me to use in my configuration.

## Acceptance Criteria
- [ ] **Scenario 1**: `agent list-models gemini` lists all available Gemini models (utilizing the API method `client.models.list()`).
- [ ] **Scenario 2**: `agent list-models openai` lists available OpenAI models (utilizing `client.models.list()`).
- [ ] **Scenario 3**: `agent list-models gh` lists available GitHub Models (via `gh` CLI).
- [ ] **Scenario 4**: `agent list-models` (without args) lists models for the currently active/default provider.
- [ ] **Negative Test**: Returns a clear error if the provider is not configured or if the API key is missing.

## Non-Functional Requirements
- **Performance**: Should be relatively fast, though it depends on API latency.
- **Usability**: Output should be clean and readable (e.g., a table or list).

## Linked ADRs
- N/A

## Impact Analysis Summary
- **Components touched**: CLI (`agent/cli.py`, `agent/commands/list.py` or new `models.py`), AI Service (`agent/core/ai/service.py`).
- **Workflows affected**: None (new command).
- **Risks identified**: Low risk.

## Test Strategy
- Unit tests mocking the AI service responses.
- Integration test with real providers (if keys available in CI, otherwise skipped).

## Rollback Plan
- Revert code changes.
