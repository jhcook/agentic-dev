# INFRA-144: New Domains Web Testing Deps and Context

## State

REVIEW_NEEDED

## Problem Statement

The current toolset lacks capabilities that best-in-class coding agents provide: web access (fetching docs/URLs), structured test execution, dependency management, and edit checkpoint/rollback. This story adds four new domain modules to close these gaps.

Parent: INFRA-098

## User Story

As a **Platform Developer**, I want **web, testing, dependency, and context management tools** so that **the agent can fetch documentation, run structured tests, manage packages, and checkpoint/rollback during multi-step edits.**

## Acceptance Criteria

- [ ] **AC-1**: `agent/tools/web.py` implements: `fetch_url` (HTTP GET → markdown conversion), `read_docs` (fetch + clean for LLM consumption).
- [ ] **AC-2**: `agent/tools/testing.py` implements: `run_tests` (structured pass/fail/coverage output), `run_single_test`, `coverage_report`.
- [ ] **AC-3**: `agent/tools/deps.py` implements: `add_dependency` (wraps `uv add`), `audit_dependencies` (wraps `pip-audit`/safety), `list_outdated`.
- [ ] **AC-4**: `agent/tools/context.py` implements: `checkpoint` (snapshot working tree), `rollback` (restore to checkpoint), `summarize_changes` (diff since last checkpoint).
- [ ] **AC-5**: `run_tests` returns structured JSON with `passed`, `failed`, `errors`, `coverage_pct` fields — not raw stdout.
- [ ] **Negative Test**: `fetch_url` with an unreachable URL returns a clear timeout error.
- [ ] **Negative Test**: `rollback` with no checkpoint returns a clear "no checkpoint" error.

## Non-Functional Requirements

- Security: `fetch_url` enforces a timeout and max response size to prevent resource exhaustion.
- Performance: `checkpoint` uses git stash or lightweight file snapshots — not full copies.

## Linked ADRs

- ADR-043: Tool Registry Foundation
- ADR-046: Audit and Observability Framework

## Linked Journeys

- JRN-072: Terminal Console TUI Chat

## Impact Analysis Summary

Components touched: 
- `web.py`, `testing.py`, `deps.py`, `context.py` (all NEW in `.agent/src/agent/tools/`)
- `.agent/src/agent/tools/interfaces.py` and `.agent/src/agent/tools/__init__.py`
- `.agent/src/agent/core/governance/audit_handler.py` and `.agent/tests/agent/core/governance/test_audit_handler.py`
- `.agent/src/agent/core/net_utils.py` and `.agent/src/agent/utils/tool_security.py`
- `.agent/etc/agent.yaml`
- `.agent/docs/tools_reference.md` and `CHANGELOG.md`
- Tests: `.agent/tests/agent/tools/test_context.py`, `test_deps.py`, `test_testing.py`, `test_web.py`
- Utils: `.agent/src/agent/utils/rollback_infra_144.py`, `verify_infra_144.py`

Workflows affected: Documentation access, test execution, dependency management, edit safety, structured logging, OpenTelemetry tracing.
Risks identified: `context.py` checkpoint strategy needs careful design — git stash vs file copies.

## Test Strategy

- Unit tests for each tool with mocked subprocess/HTTP.
- Integration test: checkpoint → edit → rollback verifies file restoration.
- Integration test: `run_tests` parses real pytest output into structured result.
- *Note: the coverage_report and full coverage_pct scraping features are explicitly deferred to a future iteration.*

## Rollback Plan

Delete the 4 new modules — no existing code depends on them.

## Copyright

Copyright 2026 Justin Cook
