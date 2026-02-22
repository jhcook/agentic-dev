# INFRA-069: Align `/panel` Workflow with `env -u VIRTUAL_ENV uv run agent panel` CLI

## State

ACCEPTED

## Goal Description

Simplify the `/panel` workflow to call `env -u VIRTUAL_ENV uv run agent panel` instead of duplicating its consultative governance logic. The CLI already supports story/runbook loading, `--base`, `--provider`, `--apply`, `--panel-engine`, and advisory output framing. The main deliverable is workflow simplification plus minor CLI verification.

## Linked Journeys

- JRN-058: Panel Consultation Workflow

## Panel Review Findings

- **@Architect**: The `panel()` function already exists in `check.py` (line 1473) with full feature parity — story loading, consultative framing, smart argument parsing, and `--apply`. No new code needed, just workflow simplification. Aligns with the ADR-030 Workflow-Calls-CLI pattern established in INFRA-068.
- **@QA**: The existing `test_panel.py` covers basic invocation. Add a negative test for no-changes scenario per AC. Verify advisory framing (no BLOCK/PASS) in output.
- **@Security**: The `panel()` function already scrubs sensitive data via `scrub_sensitive_data()`. No new security concerns from workflow simplification.
- **@Product**: AC1-AC3 are already satisfied by the existing CLI. AC4 (workflow simplification) is the primary deliverable.
- **@Observability**: No new logging needed — `panel()` already uses structured console output.
- **@Docs**: Update `/panel` workflow. Ensure `env -u VIRTUAL_ENV uv run agent panel --help` is accurate.
- **@Compliance**: No GDPR/SOC2 impact.

## Targeted Refactors & Cleanups

- [ ] Simplify `/panel` workflow from 59-line manual process to CLI-first instructions
- [ ] Verify AC3: advisory mode framing (no BLOCK/PASS in panel output)
- [ ] Add negative test: no staged changes + no story → appropriate behavior
- [ ] Update CHANGELOG

## Implementation Steps

### 1. Simplify the `/panel` Workflow

#### [MODIFY] .agent/workflows/panel.md

Replace the 59-line manual simulation (adopt personas, conduct consultations, output report template) with:

```markdown
1. Run `env -u VIRTUAL_ENV uv run agent panel <STORY-ID>` for consultative governance review.
2. Run `env -u VIRTUAL_ENV uv run agent panel <STORY-ID> --base main` to compare against a specific branch.
3. Run `env -u VIRTUAL_ENV uv run agent panel <STORY-ID> --apply` to auto-apply panel advice to story/runbook.
4. Run `env -u VIRTUAL_ENV uv run agent panel "How should we approach X for INFRA-069?"` for design discussion.
```

Retain the "PURPOSE" section explaining consultative vs. preflight distinction.

### 2. Verify Advisory Mode (AC3)

No code changes expected — verify that `convene_council_full()` output uses "Advice" and "Recommendations" framing, not BLOCK/PASS. If it uses BLOCK/PASS, adjust the prompt template.

### 3. Add Negative Test

#### [MODIFY] .agent/tests/commands/test_panel.py

- `test_panel_no_changes_no_story` — no staged changes + no story ID → error with clear message

### 4. Update CHANGELOG

#### [MODIFY] CHANGELOG.md

Add INFRA-069 entry for workflow simplification.

## Files

| File | Action | Description |
|------|--------|-------------|
| `.agent/workflows/panel.md` | MODIFY | Replace manual simulation with CLI calls |
| `.agent/tests/commands/test_panel.py` | MODIFY | Add negative test |
| `CHANGELOG.md` | MODIFY | Add INFRA-069 entry |

## Verification Plan

### Automated Tests

- [ ] Existing panel tests still pass
- [ ] New negative test passes
- [ ] AC3 verified: no BLOCK/PASS in panel output

### Manual Verification

- [ ] Run `env -u VIRTUAL_ENV uv run agent panel INFRA-069` and check consultative output
- [ ] Verify `/panel` workflow calls CLI correctly
- [ ] Confirm `env -u VIRTUAL_ENV uv run agent panel --help` shows all flags

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated
- [ ] `/panel` workflow simplified

### Testing

- [ ] Existing tests pass
- [ ] Negative test added and passes
