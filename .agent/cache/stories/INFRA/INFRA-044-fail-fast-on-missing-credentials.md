# INFRA-044: Fail Fast on Missing Credentials

## State

COMMITTED

## Problem Statement

The `agent preflight` command fails in CI environments (e.g., GitHub Actions) with a `MissingCredentialsError` for `GOOGLE_API_KEY` even when AI features are not requested (`--ai` not passed). This regression was caused by two issues: (1) preflight being unconditionally wrapped with `with_creds` in `main.py`, and (2) an incomplete rename of the Gemini API key environment variable from `GOOGLE_API_KEY` to `GEMINI_API_KEY`.

## User Story

As a developer running `agent preflight` in CI, I want the command to succeed without requiring LLM API keys so that non-AI governance checks are not blocked by missing credentials.

## Acceptance Criteria

- [x] **Scenario 1**: Given a CI environment with no LLM API keys, When `agent preflight` is run without `--ai`, Then it completes successfully without credential errors.
- [x] **Scenario 2**: Given a CI environment with no LLM API keys, When `agent preflight --ai` is run, Then it fails gracefully with a clear "Missing Credentials" message referencing `GEMINI_API_KEY`.
- [x] **Scenario 3**: Given `GEMINI_API_KEY` is set (the canonical name), When any credential validation occurs for the `gemini` provider, Then it is accepted without requiring the legacy `GOOGLE_API_KEY`.
- [x] **Negative Test**: System handles locked Secret Manager, missing env vars, and uninitialized secret stores gracefully without crashing.

## Non-Functional Requirements

- Performance: No additional latency — credential checks are inline conditionals
- Security: Credential values are never logged, only key names appear in error messages
- Compliance: SOC2 audit logging preserved (`AUDIT: Missing critical credentials` warning)
- Observability: Clear error messages guide remediation (`export GEMINI_API_KEY=...` or `agent onboard`)

## Linked ADRs

- N/A

## Linked Journeys

- N/A

## Impact Analysis Summary

Components touched: `main.py`, `check.py`, `credentials.py`, `config.py`
Workflows affected: `agent preflight`, `agent preflight --ai`, `_get_enabled_providers`, `is_ai_configured`
Risks identified: Backward compatibility with `GOOGLE_API_KEY` — mitigated by keeping it as a fallback in all checked locations

## Test Strategy

Comprehensive regression test suite added in `test_regression_credentials.py` (36 tests):

- Per-provider credential validation (all 4 providers, both env var and secret store paths)
- `with_creds` decorator isolation tests
- CLI registration source-inspection tests (prevents re-wrapping preflight)
- CI-environment simulation (no API keys + no secret store)
- Env var naming consistency checks across `credentials.py`, `service.py`, `config.py`

## Rollback Plan

Revert changes to `main.py`, `check.py`, `credentials.py`, and `config.py`. The regression tests in `test_regression_credentials.py` will immediately flag the reverted state as broken with descriptive failure messages.
