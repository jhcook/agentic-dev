# INFRA-014: AI Provider Selection and Validation

## State
COMMITTED

## Problem Statement
AI commands currently lack explicit provider control and strict input validation, leading to potential inconsistency and runtime errors when invalid providers are specified.

## User Story
As a developer, I want to be able to explicitly specify which AI provider (gh, gemini, openai) to use for any AI-powered command, and I want the system to validate my selection to ensure it's a supported and configured provider.

## Acceptance Criteria
- [x] `--provider` option added to `implement`, `match-story`, `new-runbook`, and `pr`.
- [x] `ai_service.set_provider()` validates the provider name against a whitelist (`gh`, `gemini`, `openai`).
- [x] `ai_service.set_provider()` raises `ValueError` for invalid names and `RuntimeError` for unconfigured providers.
- [x] Documentation in `commands.md` updated to reflect the new option.
- [x] Test coverage added in `test_implement.py`, `test_runbook.py`, and `test_basic_commands.py`.

## Non-Functional Requirements
- Performance
- Security
- Compliance
- Observability

## Linked ADRs
- ADR-XXX

## Impact Analysis Summary
Components touched:
Workflows affected:
Risks identified:

## Test Strategy
- **Unit Tests**:
    - Verify `AIService.set_provider` validation logic (valid, invalid, unconfigured).
    - Verify `AIService` defaults to `gh`.
    - Verify `metrics` counter is incremented on success.
- **Integration Tests**:
    - Test `env -u VIRTUAL_ENV uv run agent implement --provider` flag works for all inputs.
    - Test fallback logic when primary provider fails.
- **Manual Verification**:
    - Run `env -u VIRTUAL_ENV uv run agent preflight --provider=gh` and check logs for structured output.How will we verify correctness?

## Rollback Plan
How do we revert safely?
