# INFRA-055: Introduce User Journeys as First-Class Artifacts

## State

COMMITTED

## Problem Statement

AI agents currently have no stable behavioral contract to reference when generating or modifying code. Changes to one feature frequently break existing user flows because the agent has no awareness of how code maps to end-to-end user journeys. There is no mechanism to define "what the system should do from the user's perspective" as a persistent, machine-readable artifact that survives across conversations and runbooks.

This results in:

- **Regressions** — agent modifies shared code without understanding downstream impact
- **AI drift** — generated code diverges from intended behavior over iterative changes
- **No traceability** — no link between user intent, code implementation, and test coverage

## User Story

**As a** developer using the agentic workflow, **I want** to define user journeys as structured YAML artifacts with implementation mappings, **so that** the AI agent understands existing behavioral contracts and avoids breaking them when implementing new features.

**As a** QA engineer, **I want** journeys to generate test hints and track which test files verify each step, **so that** I can ensure complete coverage of critical user flows.

**As a** product manager, **I want** a human-readable definition of each user journey with actors, preconditions, and expected outcomes, **so that** I can validate the system's behavior against business requirements.

## Acceptance Criteria

### YAML Spec & Template

- [ ] **Journey YAML schema** is defined with required fields: `id`, `title`, `actor`, `description`, `steps`
- [ ] **Safe defaults** for all optional fields (`state: DRAFT`, `priority: medium`, `auth_context.level: public`, etc.)
- [ ] **`schema_version`** field included for forward compatibility (v1)
- [ ] **Step-level `implementation` mapping** supports `routes`, `files` (with type annotations), and `tests` — treated as *advisory*, not authoritative
- [ ] **Top-level `implementation_summary`** aggregates entry point, components, and test suite
- [ ] **Error paths** can reference `trigger_step` with `condition`, `system_response`, `assertions`, and `severity`
- [ ] **Edge cases** support `scenario`, `expected`, and `severity`
- [ ] **`data_classification`** field on `data_state` entities (public/internal/confidential/restricted)
- [ ] **Composition** supports `depends_on` (prerequisites); `extends` and `branches` reserved for follow-up story
- [ ] **Pydantic model** (`JourneySpec`) validates YAML schema at load time with typed fields and defaults
- [ ] **Journey template** created at `.agent/templates/journey-template.yaml`

### CLI Commands

- [ ] `agent new-journey [JRN-XXX]` creates a journey from the template with auto-ID generation
- [ ] `agent list-journeys` scans and displays all journeys with ID, title, state, and actor
- [ ] `agent validate-journey` validates YAML against Pydantic schema — malformed journeys fail fast with clear errors
- [ ] All commands registered in `main.py`
- [ ] All YAML loading uses `yaml.safe_load()` — never `yaml.load()`

### Config & Sync

- [ ] `journeys_dir` added to `Config` class pointing to `.agent/cache/journeys/`
- [ ] `sync.py` handles `journey` type in `_write_to_disk`, `scan`, and `flush`

### Agent Context Integration

- [ ] `agent new-runbook` injects existing journey context into the AI prompt (sanitized to prevent prompt injection)
- [ ] `agent implement` loads journey implementation mappings to detect file overlap and prevent regressions
- [ ] **Negative test**: Modifying a file that backs a journey step triggers a warning during preflight
- [ ] Overlap warnings surface in preflight output and PR description

### ADR

- [ ] ADR-024 status updated from `PROPOSED` to `ACCEPTED`

## Non-Functional Requirements

- **Performance**: Journey loading should not add >200ms to CLI commands
- **Security**: No secrets or PII in journey YAML files; `yaml.safe_load()` enforced; journey content sanitized before LLM prompt injection
- **Compliance**: Journeys follow the same Apache 2.0 license header convention as other artifacts; `data_classification` field prevents accidental PII in examples
- **Observability**: Journey count and coverage metrics available via `agent list-journeys`; structured logging for `journey_loaded`, `journey_validation_failed`, `journey_overlap_detected` events

## Linked ADRs

- ADR-024: Introduce User Journeys

## Impact Analysis Summary

**Components touched**: `config.py`, `main.py`, `journey.py` (new), `list.py`, `sync.py`, `runbook.py`, `implement.py`
**Workflows affected**: `new-runbook`, `implement`, `preflight`, `sync push/pull`
**Risks identified**: Increased runbook complexity from journey context injection; test suite growth from journey-derived tests

## Test Strategy

- **Unit tests** for `new-journey` CLI command (interactive creation, auto-ID, template population)
- **Unit tests** for `list-journeys` command (scan, display, empty state)
- **Unit tests** for sync integration (write-to-disk mapping, scan inclusion, flush cleanup)
- **Integration test** for journey context injection in `new-runbook` and `implement`
- **Full regression suite** via `agent preflight` to confirm no existing tests break

## Rollback Plan

All changes are additive (new files, new config paths, new command registrations). Rollback is a git revert of the implementation commit. No data migrations or schema changes required — journeys are plain YAML files on disk.
