# INFRA-070: Align `/pr` Workflow with `env -u VIRTUAL_ENV uv run agent pr` CLI

## State

COMMITTED

## Problem Statement

The `/pr` workflow has the agent manually run preflight checks, generate a PR body from a template, and then call `gh pr create --web`. The CLI command `env -u VIRTUAL_ENV uv run agent pr` exists but the workflow duplicates its logic with manual agent steps. The PR creation process (preflight → body generation → `gh` invocation) should be fully encapsulated in the CLI.

## User Story

As a developer using `/pr`, I want the workflow to call `env -u VIRTUAL_ENV uv run agent pr` so that PR creation is a single CLI invocation that handles preflight, body generation, and GitHub CLI execution.

## Acceptance Criteria

- [ ] **AC1: Preflight Integration**: `env -u VIRTUAL_ENV uv run agent pr` runs `env -u VIRTUAL_ENV uv run agent preflight --ai` as a prerequisite step, failing if preflight returns BLOCK.
- [ ] **AC2: Auto-Generated Body**: `env -u VIRTUAL_ENV uv run agent pr` generates the PR body from the template (Story Link, Changes summary, Governance status).
- [ ] **AC3: Title Format**: `env -u VIRTUAL_ENV uv run agent pr` auto-generates the title as `[STORY-ID] <description>`.
- [ ] **AC4: GitHub Invocation**: `env -u VIRTUAL_ENV uv run agent pr` calls `gh pr create` with the generated title and body.
- [ ] **AC5: Body Scrubbing**: PR body is passed through `scrub_sensitive_data()` before being sent to GitHub.
- [ ] **AC6: Skip Preflight**: `env -u VIRTUAL_ENV uv run agent pr --skip-preflight` allows skipping preflight (audit-logged with timestamp).
- [ ] **AC7: Workflow Simplification**: `/pr` workflow is reduced to calling `env -u VIRTUAL_ENV uv run agent pr`, with "See Also: `env -u VIRTUAL_ENV uv run agent pr --help`".
- [ ] **Negative Test**: `env -u VIRTUAL_ENV uv run agent pr` fails gracefully if `gh` CLI is not installed.

## Non-Functional Requirements

- **Security**: No secrets in generated PR body.
- **Compliance**: Preflight must pass before PR creation (unless explicitly skipped).

## Linked ADRs

- ADR-025

## Linked Journeys

- JRN-059 (PR Creation Workflow)

## Impact Analysis Summary

Components touched: `workflow.py` (pr command), `pr.md` workflow
Workflows affected: `/pr`
Risks identified: `gh` CLI availability; GitHub authentication state.

## Test Strategy

- **Unit test**: Verify `env -u VIRTUAL_ENV uv run agent pr` generates correct title and body format.
- **Unit test**: Verify preflight integration (mock subprocess).
- **Manual**: Run `env -u VIRTUAL_ENV uv run agent pr` on a feature branch and verify PR creation.

## Rollback Plan

Revert CLI changes. Workflow can remain as manual fallback.
