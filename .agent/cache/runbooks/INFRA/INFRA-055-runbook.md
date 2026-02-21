# INFRA-055: Introduce User Journeys as First-Class Artifacts

## State

ACCEPTED

## Goal Description

Introduce user journeys as first-class, version-controlled YAML artifacts into the agentic workflow. Journeys define behavioral contracts (who does what, what happens, what to assert) that the agent uses during runbook generation and implementation to prevent regressions. A journey must exist before implementation can occur — they are prerequisites, not documentation.

Implements ADR-024.

## Panel Review Findings

**@Architect:**
PASS. The design follows established patterns — `journey.py` mirrors `story.py`, config follows existing `*_dir` convention, sync follows the same type-mapping pattern. Layer boundaries are respected: CLI commands in `commands/`, no core-layer imports from CLI. The `JRN-` prefix is consistent with the `ADR-` naming convention. The YAML schema uses a `schema_version` field for forward compatibility. One concern: journey context injection into prompts must be size-bounded to avoid token exhaustion — the implementation plan already addresses this with a 5000-char truncation. ADR-024 provides the architectural justification.

**@Security:**
PASS with conditions. Three mandatory controls:

1. `yaml.safe_load()` must be used for all YAML parsing — `yaml.load()` is prohibited (prevents arbitrary code execution).
2. Journey content injected into LLM prompts must be scrubbed via `scrub_sensitive_data()` to prevent prompt injection.
3. The `data_classification` field on `data_state` entities must default to `internal` — no PII should appear in journey examples.
No secrets are stored in journey files. No new network calls introduced. Dependency surface is unchanged (`pyyaml` already in the project).

**@QA:**
PASS. Test strategy is comprehensive: unit tests for CLI commands (new-journey, list-journeys, validate-journey), unit tests for sync integration, and integration testing via `env -u VIRTUAL_ENV uv run agent preflight`. The Pydantic model provides schema validation — malformed YAML fails fast. Negative test for overlap detection (modifying a file that backs a journey step triggers a warning) is explicitly called out in the story's AC. The `CRITICAL_FLOWS.mdc` should be updated to reference journey-backed flows once journeys are populated.

**@Product:**
PASS. Acceptance criteria are clear and testable. The user story covers three personas (developer, QA, PM). The workflow order — Journey → Story → Runbook → Implement — enforces that behavioral intent is defined before code is written. Impact analysis identifies all touched components. The `linked_journeys` field on stories creates bidirectional traceability.

**@Observability:**
PASS with additions. Structured logging events should be emitted for: `journey_created`, `journey_loaded`, `journey_validation_failed`, `journey_overlap_detected`. These should use the existing `console.print` pattern (no external logging framework required at this stage). The `env -u VIRTUAL_ENV uv run agent list-journeys` command provides runtime visibility into journey count and coverage. Future: metrics for journey-to-test coverage ratio.

**@Docs:**
PASS. `user_journeys.md` already created in `.agent/docs/` with full lifecycle documentation. CHANGELOG.md must be updated. The `journey-template.yaml` serves as inline documentation for the YAML schema. ADR-024 documents the architectural decision. No OpenAPI changes required (CLI-only feature).

**@Compliance:**
PASS. Apache 2.0 license headers required on all new `.py` files (`journey.py`, test files). YAML templates don't require license headers. No PII handling introduced — the `data_classification` field is metadata about journey data, not actual user data. No GDPR implications (journeys describe system behavior, not user data). The `yaml.safe_load()` enforcement aligns with SOC2 secure coding requirements.

## Data Handling & Compliance

- **Data Content**: Journeys contain behavioral contracts (system behavior descriptions), not personal data. The `data_classification` field defaults to `internal`.
- **PII Prevention**: All journey content injected into AI prompts is scrubbed via `scrub_sensitive_data()`. Template placeholders use generic personas, not real user data.
- **Lawful Basis**: Not applicable — journeys describe system behavior, not data subject information. No GDPR processing activity is introduced.
- **Retention**: Journey YAML files persist as version-controlled repository artifacts for the lifetime of the project.
- **Deletion**: Journeys can be removed via `git rm`, `env -u VIRTUAL_ENV uv run agent sync flush`, or by archiving the containing repository.

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Add `journeys_dir` property to `Config` alongside existing dirs (one-liner, maintains pattern consistency)
- [ ] Update `state-enforcement.mdc` to document the Journey → Story prerequisite constraint

## Implementation Steps

### 1. Core Configuration

#### [MODIFY] `.agent/src/agent/core/config.py`

- Add `self.journeys_dir = self.cache_dir / "journeys"` immediately after `self.runbooks_dir`
- Ensure `journeys_dir` is created via `mkdir(parents=True, exist_ok=True)` in the init block alongside other dirs

### 2. YAML Template

#### [NEW] `.agent/templates/journey-template.yaml`

Create the journey template with the full schema, safe defaults, and comments:

```yaml
# Journey: JRN-XXX
# Title: <Title>
# State: DRAFT

schema_version: 1

id: "JRN-XXX"
title: "<Title>"
state: DRAFT
priority: medium

actor: "<user persona>"
description: "<what this journey achieves>"

preconditions: []

steps:
  - id: 1
    action: "<user action>"
    system_response: "<expected system behavior>"
    assertions:
      - "<verifiable outcome>"
    implementation:
      routes: []
      files: []
      tests: []

acceptance_criteria:
  - "<criterion 1>"

error_paths: []
edge_cases: []
data_state:
  requires: []
  mutates: []

auth_context:
  level: public
  permissions: []

linked_stories: []
linked_adrs: []

implementation_summary:
  entry_point: null
  components: []
  test_suite: null

test_hints:
  framework: pytest
  fixtures: []
  tags: []

depends_on: []
```

### 3. CLI Commands

#### [NEW] `.agent/src/agent/commands/journey.py`

Follow the exact pattern of `story.py`:

- `new_journey(journey_id, ai, provider)`:
  - **Arguments**:
    - `journey_id` (optional) — auto-generate via `get_next_id()` with `JRN-` prefix if omitted
    - `--ai` (bool, default False) — when set, uses AI service to generate populated journey content
    - `--provider` (optional) — force AI provider (gh, gemini, openai), same pattern as `runbook.py`
  - **Without `--ai`** (default):
    - Prompt for title
    - Read `journey-template.yaml`, replace `JRN-XXX` with actual ID and `<Title>` with actual title
    - Write scaffold to `config.journeys_dir / f"{journey_id}-{safe_title}.yaml"`
  - **With `--ai`**:
    - Prompt for title and a brief description (one-liner of the user goal)
    - Load context via `context_loader.load_context()` (existing journeys, rules, ADRs)
    - Load journey schema spec from `.agent/docs/journey_yaml_spec.md`
    - Build prompt instructing AI to generate a fully populated YAML journey matching the schema
    - Call `ai_service.complete(system_prompt, user_prompt)` — same pattern as `runbook.py`
    - Parse response, validate it has required fields (`id`, `title`, `actor`, `description`, `steps`)
    - Write the AI-generated YAML to disk
    - Scrub via `scrub_sensitive_data()` before any AI calls
  - **Common (both paths)**:
    - Upsert to local DB via `upsert_artifact()`
    - Auto-sync via `push_safe()`
    - Include Apache 2.0 license header

- `validate_journey(journey_id)`:
  - Find the YAML file in `config.journeys_dir`
  - Use `yaml.safe_load()` to parse
  - Validate required fields: `id`, `title`, `actor`, `description`, `steps`
  - Print validation result (pass/fail with specific errors)
  - Exit 1 on failure

#### [MODIFY] `.agent/src/agent/commands/list.py`

Add `list_journeys()` function:

- Scan `config.journeys_dir` recursively for `*.yaml` files
- For each file: `yaml.safe_load()`, extract `id`, `title`, `state`, `actor`
- Display in a Rich table (same pattern as `list_stories()`)

#### [MODIFY] `.agent/src/agent/main.py`

Register the new commands:

```python
from agent.commands import journey
app.command(name="new-journey")(journey.new_journey)
app.command(name="validate-journey")(journey.validate_journey)
app.command(name="list-journeys")(list_cmd.list_journeys)
```

### 4. Sync Integration

#### [MODIFY] `.agent/src/agent/sync/sync.py`

Three targeted changes:

1. **`_write_to_disk()`** — add `journey` type mapping to `config.journeys_dir`
2. **`scan()`** — add `(Path(".agent/cache/journeys"), "journey")` to paths_to_scan, use `.yaml` extension
3. **`flush()`** — add `config.journeys_dir` to `artifact_dirs` list

### 5. Agent Context Integration

#### [MODIFY] `.agent/src/agent/commands/runbook.py`

Inject journey context into the runbook generation prompt:

- After loading story content (line ~90), load all journeys from `config.journeys_dir`
- Concatenate journey YAML content, truncated to 5000 chars to avoid token limits
- Scrub via `scrub_sensitive_data()` before injection
- Append to `user_prompt` as: `EXISTING USER JOURNEYS:\n{journeys_content}`
- Include instruction: "These journeys define existing behavioral contracts. Do not break them when designing the implementation plan."

#### [MODIFY] `.agent/src/agent/commands/implement.py`

Add journey prerequisite gate and context injection:

- **New argument**: `--skip-journey-check` (bool, default False)
- **Journey Gate** (before any implementation logic):
  1. Read the story file, parse `## Linked Journeys` section for journey IDs (e.g., `JRN-001`)
  2. If `linked_journeys` is empty or only contains placeholder `JRN-XXX`:
     - If `--skip-journey-check` is set: emit `⚠️ Skipping journey check` and proceed
     - Otherwise: `❌ No journeys linked to this story. Define journeys first with 'agent new-journey', or use --skip-journey-check to proceed.` → exit 1
  3. For each linked journey ID, check `config.journeys_dir` for matching YAML file
     - If missing: `❌ Journey JRN-XXX not found. Run 'agent new-journey JRN-XXX' first.` → exit 1
  4. If all exist: `✅ Journey gate passed: {n} journey(s) loaded`
- **Context injection** (existing, enhanced):
  - Load all journey YAML files from `config.journeys_dir`
  - Parse `implementation.files` from each journey step to build a map of journey-backed files
  - Inject this context into the system prompt with instruction: "These files are mapped to existing user journeys. Modifications must preserve all journey assertions."
  - After implementation, compare changed files against journey-backed files and emit warnings

#### [MODIFY] `.agent/templates/story-template.md`

Add `## Linked Journeys` section after `## Linked ADRs` with placeholder `- JRN-XXX`.

#### [MODIFY] `.agent/templates/runbook-template.md`

Add `## Linked Journeys` section after `## Goal Description` with placeholder `- JRN-XXX: <Journey title>`.

### 6. ADR Update

#### [MODIFY] `.agent/adrs/ADR-024-introduce-user-journeys.md`

- Change `## Status` from `PROPOSED` to `ACCEPTED`
- Add `## Changes` section: `- **2026-02-12**: Status updated to ACCEPTED. Implementation via INFRA-055.`

## Verification Plan

### Automated Tests

#### [NEW] `.agent/tests/commands/test_journey.py`

- `test_new_journey_interactive` — mock prompts, verify YAML file created with correct content
- `test_new_journey_with_explicit_id` — pass `JRN-001`, verify file at expected path
- `test_new_journey_with_ai` — mock AI service, verify populated YAML output
- `test_new_journey_duplicate` — verify error on duplicate ID
- `test_list_journeys` — create sample YAML files, verify list output
- `test_validate_journey_valid` — well-formed YAML passes validation
- `test_validate_journey_missing_fields` — YAML missing required fields fails with clear error
- `test_validate_journey_uses_safe_load` — ensure `yaml.load()` is never called
- `test_implement_journey_gate_blocks_no_journeys` — story with no linked journeys exits 1
- `test_implement_journey_gate_blocks_missing_file` — story links JRN-001 but file doesn't exist, exits 1
- `test_implement_journey_gate_passes` — story links JRN-001, file exists, proceeds
- `test_implement_journey_gate_skip_flag` — `--skip-journey-check` bypasses gate

Run:

```bash
cd /Users/jcook/repo/agentic-dev/.agent && python3 -m pytest tests/commands/test_journey.py -v
```

### Regression Check

Run full suite to confirm no breakage:

```bash
cd /Users/jcook/repo/agentic-dev/.agent && python3 -m pytest tests/ -v --tb=short
```

### Manual Verification

- [ ] Run `env -u VIRTUAL_ENV uv run agent new-journey` → verify YAML file appears in `.agent/cache/journeys/`
- [ ] Run `env -u VIRTUAL_ENV uv run agent list-journeys` → verify output shows the journey with correct fields
- [ ] Run `env -u VIRTUAL_ENV uv run agent validate-journey JRN-001` → verify pass
- [ ] Create a malformed YAML journey manually → run `validate-journey` → verify fail with clear error
- [ ] Run `env -u VIRTUAL_ENV uv run agent new-runbook` for a new story → verify journey context appears in the generated runbook
- [ ] Inspect runbook output for journey overlap warnings (if applicable)

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated with "Added: User Journeys (INFRA-055, ADR-024)"
- [ ] `.agent/docs/user_journeys.md` already created (done in planning phase)
- [ ] ADR-024 status updated to ACCEPTED

### Observability

- [ ] Logs are structured and free of PII
- [ ] `journey_created`, `journey_loaded` events logged via `console.print`

### Testing

- [ ] Unit tests passed
- [ ] Regression suite passed (`env -u VIRTUAL_ENV uv run agent preflight` or `pytest tests/`)
