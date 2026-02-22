# INFRA-071: Add Panel Consultation to `env -u VIRTUAL_ENV uv run agent new-journey`

## State

ACCEPTED

## Goal Description

Add a `--panel` flag to `env -u VIRTUAL_ENV uv run agent new-journey` that automatically runs a consultative panel review of the generated journey YAML. This replaces the manual Step 3 in the `/journey` workflow. The panel flag requires `--offline` (panel reviews AI-generated content).

## Linked Journeys

- JRN-060: Journey Creation Workflow

## Panel Review Findings

- **@Architect**: The `new_journey()` function already handles AI generation and file writing. The `--panel` flag should be added after the file write, calling `convene_council_full()` in consultative mode with the journey content as context. Reuses existing panel infrastructure from `check.py`.
- **@QA**: Add tests for: (1) `--panel` triggers consultation, (2) `--panel` without `--offline` errors, (3) panel feedback is appended to journey file.
- **@Security**: Panel consultation uses `scrub_sensitive_data()` on journey content before AI analysis. No new security surface.
- **@Product**: AC1-AC4 deliver real value — integrating governance feedback into journey creation removes a manual orchestration step.
- **@Observability**: Log panel consultation result with journey ID.
- **@Compliance**: No GDPR/SOC2 impact.

## Implementation Steps

### 1. Add `--panel` Flag to `new_journey()`

#### [MODIFY] .agent/src/agent/commands/journey.py

- Add `panel: bool = typer.Option(False, "--panel", help="Run panel consultation after generation (requires).")`
- After file write (line ~240), if `--panel` is set:
  - Validate `--offline` was also set; if not, error with clear message
  - Load the generated journey content
  - Call `convene_council_full()` in consultative mode with journey content
  - Append panel feedback summary as a `# Panel Feedback` comment block at end of YAML file
- Import `convene_council_full` from `agent.commands.check` (lazy, inside the if block)

### 2. Simplify `/journey` Workflow Step 3

#### [MODIFY] .agent/workflows/journey.md

- Replace Step 3 (manual panel consultation, ~8 lines) with:

  ```
  3. **Panel Consultation**: Use `--panel` flag: `env -u VIRTUAL_ENV uv run agent new-journey <JRN-ID> --panel`
  ```

### 3. Add Unit Tests

#### [NEW] .agent/tests/commands/test_journey_panel.py

- `test_panel_triggers_consultation` — `--offline --panel` calls `convene_council_full` in consultative mode
- `test_panel_without_ai_errors` — `--panel` alone → error with clear message

## Files

| File | Action | Description |
|------|--------|-------------|
| `.agent/src/agent/commands/journey.py` | MODIFY | Add `--panel` flag with panel consultation |
| `.agent/workflows/journey.md` | MODIFY | Simplify Step 3 to reference `--panel` |
| `.agent/tests/commands/test_journey_panel.py` | NEW | Unit tests for panel flag |
| `CHANGELOG.md` | MODIFY | Add INFRA-071 entry |

## Verification Plan

### Automated Tests

- [ ] `test_panel_triggers_consultation` passes
- [ ] `test_panel_without_ai_errors` passes
- [ ] Existing journey tests unaffected

### Manual Verification

- [ ] `env -u VIRTUAL_ENV uv run agent new-journey JRN-TEST --panel` produces journey + panel feedback
- [ ] `env -u VIRTUAL_ENV uv run agent new-journey JRN-TEST --panel` (no) errors cleanly

## Definition of Done

- [ ] CHANGELOG.md updated
- [ ] `/journey` workflow Step 3 simplified
- [ ] Unit tests pass
