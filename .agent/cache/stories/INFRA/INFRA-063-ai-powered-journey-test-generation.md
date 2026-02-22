# INFRA-063: AI-Powered Journey Test Generation

## State

COMMITTED

## Plan

[INFRA-062 Regression Guardrails](../plans/INFRA/INFRA-062-regression-guardrails.md)

## Problem Statement

INFRA-058 introduced `env -u VIRTUAL_ENV uv run agent journey backfill-tests` to generate test stubs for COMMITTED journeys, but the stubs are empty scaffolds with `pytest.skip("Not yet implemented")`. Developers must manually write every test body, which is labor-intensive across 50+ journeys. We need an `--offline` flag that leverages the AI service to generate real, working test code from journey steps, assertions, and relevant source files.

## User Story

As a developer, I want `env -u VIRTUAL_ENV uv run agent journey backfill-tests` to generate real test implementations (not just stubs) by reading each journey's steps and assertions alongside the relevant source code, so that I get meaningful regression coverage without writing every test by hand.

## Acceptance Criteria

- [ ] **AC-1**: `env -u VIRTUAL_ENV uv run agent journey backfill-tests` sends each journey's steps, assertions, and linked source files to the AI service and generates pytest test bodies with real assertions (not `pytest.skip`).
- [ ] **AC-2**: Phase 1 generates `pytest` tests for all scopes. Framework-specific generation (Playwright for WEB, Maestro for MOBILE) is deferred to a follow-up story and inferred from `implementation.framework` field when implemented.
- [ ] **AC-3**: Generated tests include `@pytest.mark.journey("JRN-XXX")` markers for targeted execution.
- [ ] **AC-4**: `--offline` generates tests and previews each in a Rich syntax panel, then prompts `Write? [y/N/all/skip]` for interactive confirmation. `--offline --write` batch-writes without prompts (CI mode). `--offline --dry-run` previews only (no prompts, no writes).
- [ ] **AC-5**: AI prompt includes relevant source code context — resolves file paths from `implementation.files` in the journey YAML, scrubs via `scrub_sensitive_data()`, and includes contents (truncated to token budget) in the prompt.
- [ ] **AC-6**: Existing test files are never overwritten. If a test file already exists, skip with a warning.
- [ ] **AC-7**: `--scope` flag filters by scope (INFRA, MOBILE, WEB, BACKEND) — same as existing stub command. `--journey JRN-XXX` targets a single journey.
- [ ] **AC-8**: Falls back to stub generation (existing behavior) if AI service is unavailable or returns an error.
- [ ] **AC-9**: All AI-generated code is validated via `ast.parse()` before writing. `SyntaxError` triggers fallback to stub with a warning comment noting the AI failure.
- [ ] **AC-10**: Generated test files include the Apache 2.0 license header and an `"""AI-generated regression tests for {jid}."""` docstring.
- [ ] **AC-11**: AI service is initialized lazily (ADR-025) — no import or instantiation at module level.
- [ ] **AC-12**: Rich progress bar shown when processing multiple journeys with AI.
- [ ] **Negative Test**: Malformed AI responses (non-parseable Python, syntax errors) are caught and reported — stub is generated instead with a comment noting the AI failure.

## Non-Functional Requirements

- **Performance**: Token budget per journey capped at configurable limit (default: 8k tokens source context).
- **Security**: No secrets, PII, or credentials included in AI prompts. Source files are scrubbed using `scrub_sensitive_data()` from `security.py`. Source paths are validated to remain within the repository root.
- **Compliance**: SOC 2 CC7.1 — generated test code must be reviewed before merging. Enforced by `--offline` defaulting to dry-run mode (AC-4).
- **Observability**: Structured logging for each AI generation call with fields: `journey_id`, `scope`, `token_count`, `duration_s`, `status` (success/fallback/error). Summary metric emitted at end: total processed, AI successes, fallbacks, skips, errors.

## Linked ADRs

- ADR-005 (AI-Driven Governance Preflight)
- ADR-025 (Lazy Initialization)

## Linked Journeys

- JRN-053 (Journey Test Coverage)

## Linked Stories

- INFRA-058 (Journey-Linked Regression Tests) — prerequisite, provides the `backfill-tests` command and journey schema

## Panel Advice Applied

Source: [Panel Consultation INFRA-063](../../../../.gemini/antigravity/brain/2911b6dc-95d3-4c5f-84b1-ea3833073209/panel_consultation_infra063.md)

- AC-2 phased to pytest-only (Phase 1) per Mobile/Web leads
- AC-4 changed to dry-run default per Product/Compliance
- AC-5 updated with `scrub_sensitive_data()` per Security/Compliance
- AC-7 extended with `--journey` flag per Product
- AC-9 added for `ast.parse()` validation per Architect/QA/Security/Backend
- AC-10 added for license headers per Compliance
- AC-11 added for lazy init per Backend (ADR-025)
- AC-12 added for progress bar per Product
- NFR Observability expanded with specific log fields per SRE
- Impact Analysis updated with refactoring plan per Architect/Backend
- Test Strategy enhanced with edge cases per QA

## Impact Analysis Summary

Components touched: `journey.py` (refactor `backfill_tests` into `_iter_eligible_journeys()`, `_generate_stub()`, `_generate_ai_test()` helpers), `prompts.py` (new `generate_test_prompt()`)
Workflows affected: `env -u VIRTUAL_ENV uv run agent journey backfill-tests` gains `--offline` and `--write` flags
Risks identified: AI-generated code quality varies; mitigated by `ast.parse()` gate and dry-run default

## Test Strategy

### Unit Tests

- Mock AI service to return known test code, verify file write
- Mock AI service to return malformed code, verify `ast.parse()` catches it and falls back to stub
- Verify `--offline` defaults to dry-run (no file writes without `--write`)
- Verify `--scope` and `--journey` filtering
- Verify token budget truncation of source context
- Verify `scrub_sensitive_data()` is applied to source context before prompt
- Edge case: journey with `implementation.files` pointing to non-existent files — logs warning, continues
- Edge case: journey with 0 steps — skips gracefully with warning
- Verify generated files include license header

### Integration Tests

- End-to-end: `env -u VIRTUAL_ENV uv run agent journey backfill-tests` with a real journey file (dry-run default)
- Verify generated test is syntactically valid Python (`ast.parse`)

## Rollback Plan

Remove `--offline` and `--write` flag handling from `backfill_tests` command. Existing stub behavior is the default and remains unchanged.
