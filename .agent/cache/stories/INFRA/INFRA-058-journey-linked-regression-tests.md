# INFRA-058: Journey-Linked Regression Tests

## State

COMMITTED

## Problem Statement

User journeys define behavioral contracts but have no enforced link to the test files that verify them. The `implementation.tests` field in journey YAML is either empty or not validated. This means a journey can exist as a "first-class artifact" (per INFRA-055) while its behavioral contract has zero automated verification. When code changes touch journey-scoped files, there is no mechanism to ensure the corresponding tests exist and pass.

## User Story

As a **developer governed by the agent framework**, I want each user journey to be linked to its regression test files so that I can't merge changes that break a journey without the test catching it.

## Acceptance Criteria

- [ ] **AC-1**: Journey YAML schema enforces `implementation.tests` as a required non-empty list for journeys in `COMMITTED` or `ACCEPTED` state. `DRAFT` journeys are exempt. Enforcement is state-aware: extend `validate_journey` (line 228 in `journey.py`) using the existing errors/warnings pattern.
- [ ] **AC-2**: `env -u VIRTUAL_ENV uv run agent validate-journey` verifies that all files listed in `implementation.tests` exist on disk. Path resolution is relative to `config.project_root`. Validation is extension-agnostic (pytest `.py`, Maestro `.yaml`, Playwright `.spec.ts` all valid). Path traversal and absolute paths outside project root are rejected.
- [ ] **AC-3**: `env -u VIRTUAL_ENV uv run agent preflight` includes a journey coverage check. **Phase 1**: coverage failures are a **warning** (not a block) because all 50+ existing journeys have `tests: []`. Flip to blocking after a target coverage threshold (e.g., 80% of COMMITTED journeys linked). A standalone `check_journey_coverage()` function in `check.py` returns structured results.
- [ ] **AC-4**: A new `env -u VIRTUAL_ENV uv run agent journey coverage` command registered on the existing `journey.py` Typer app reports journey → test mapping with a rich table: Journey ID | Title | State | Tests Linked | Status (✅/❌/⚠️). Supports `--json` flag for CI integration. Tracks coverage percentage persistently for `env -u VIRTUAL_ENV uv run agent audit`.
- [ ] **AC-5**: The journey creation workflow (`/journey`, `new_journey` function) prompts "Link test files? [paths or press Enter to generate stubs]". Default action generates test stubs, not skip.
- [ ] **AC-6**: `env -u VIRTUAL_ENV uv run agent journey backfill-tests` command auto-generates pytest test stubs from journey assertions for all COMMITTED journeys with empty `implementation.tests`. Stubs use `@pytest.mark.journey("JRN-XXX")` marker for targeted execution (`pytest -m 'journey("JRN-044")'`). Stubs contain `pytest.skip("Not yet implemented")` so they pass CI but are clearly incomplete. Stubs never overwrite existing files.
- [ ] **AC-7**: Per-file test status: a journey with `tests` containing both existing and missing files reports per-file status, not a blanket pass/fail.
- [ ] **AC-8**: Journey template (`journey-template.yaml`) updated with comment: `# Required for COMMITTED journeys. List paths to test files relative to project root.`
- [ ] **Negative Test**: A journey in `DRAFT` state is exempt from the test linkage requirement.
- [ ] **Negative Test**: `preflight` warns (Phase 1) / blocks (Phase 2) if a COMMITTED journey has no linked tests.
- [ ] **Negative Test**: A COMMITTED journey with `tests: ["tests/nonexistent.py"]` produces a "file not found" error distinct from "tests field is empty."

## Non-Functional Requirements

- Compliance: Journey-test traceability satisfies SOC 2 CC7.1 evidence requirements for regression prevention. Coverage reports persistable for `env -u VIRTUAL_ENV uv run agent audit`.
- Developer Experience: Clear error messages when tests are missing, with convention-based suggested paths (e.g., `"Consider creating: tests/journeys/test_jrn_044.py"`).
- Observability: Journey coverage metrics tracked over time via structured logging. OpenTelemetry span for coverage check in preflight.
- Performance: Coverage check scans only COMMITTED/ACCEPTED journeys; no full-repo test execution.

## Linked ADRs

- ADR-005 (AI-Driven Governance Preflight)

## Linked Journeys

- JRN-044 (Introduce User Journeys as First-Class Artifacts)
- JRN-053 (Journey Test Coverage)

## Panel Advice Applied

- **@architect**: Phased rollout (warning→blocking) due to 50+ backfill. `backfill-tests` command for migration. Coverage levels: linked/missing/unlinked/stale. (→ AC-3, AC-4, AC-6)
- **@qa**: Path resolution relative to `config.project_root`. Per-file status. Distinct error for "file not found" vs "field empty". (→ AC-2, AC-7, Negative Tests)
- **@security**: Validate against path traversal. Stubs never overwrite. (→ AC-2, AC-6)
- **@product**: Rich table output for coverage command. Convention-based path suggestions. Default action = generate stubs. (→ AC-4, AC-5)
- **@backend**: `@pytest.mark.journey` marker for targeted execution. `check_journey_coverage()` standalone function. (→ AC-3, AC-6)
- **@mobile/@web**: Extension-agnostic validation (Maestro `.yaml`, Playwright `.spec.ts`, pytest `.py`). (→ AC-2)
- **@docs**: Template comment for `tests` field. Document naming convention. (→ AC-8)
- **@compliance**: Persistable coverage report. Coverage metric tracked over time. (→ AC-4, NFRs)

## Impact Analysis Summary

Components touched:

- `.agent/src/agent/commands/journey.py` — add `coverage` and `backfill-tests` subcommands, enhance `validate_journey` with state-aware test enforcement
- `.agent/src/agent/commands/check.py` — add `check_journey_coverage()` gate to preflight (initially warning)
- `.agent/templates/journey-template.yaml` — add comment explaining `tests` field
- `.agent/cache/journeys/` — backfill `implementation.tests` in existing COMMITTED journeys

Workflows affected:

- `/preflight` — new journey coverage gate (warning Phase 1, blocking Phase 2)
- `/journey` — enhanced creation workflow with test stub generation

Risks identified:

- Backfill effort: 50+ existing journeys need `implementation.tests` populated. Mitigated by `backfill-tests` command with auto-generated stubs.
- False blocks: Phased rollout (warning first) prevents breaking existing workflows.
- Path ambiguity: Resolved by standardizing on `config.project_root` as base.

## Test Strategy

- **Unit — validate_journey**: Rejects COMMITTED journey with empty `implementation.tests`. Accepts DRAFT journey with empty tests. Rejects COMMITTED journey with nonexistent test file (distinct error). Reports per-file status for mixed existing/missing files.
- **Unit — path validation**: Path traversal (`../../etc/passwd`) rejected. Absolute paths rejected. Extension-agnostic (`.py`, `.yaml`, `.spec.ts` all valid).
- **Unit — stub generation**: `backfill-tests` generates valid pytest file with `@pytest.mark.journey` marker. No overwrite of existing files.
- **Integration — coverage command**: `env -u VIRTUAL_ENV uv run agent journey coverage` produces expected table output for fixture journeys with mixed coverage states.
- **Integration — preflight**: Preflight warns (Phase 1) on COMMITTED journey with missing tests. Journey coverage gate runs as separate section.

## Rollback Plan

- Remove the journey coverage gate from preflight.
- Revert validate-journey schema enforcement.
- Existing journeys remain valid (field stays optional until re-enabled).
- Remove generated test stubs (all in `tests/journeys/` directory).
