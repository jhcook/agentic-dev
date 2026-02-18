# INFRA-064: Standardize --ai Flag Behavior Across CLI Commands

## State

DRAFT

## Plan

### Problem Statement

The `--ai` flag appears in 7 commands across 5 files, but each command implements it differently. Some write output directly, others preview to stdout, and there is no consistent interactive confirm UX. INFRA-063 introduced a generate → preview → confirm pattern for `backfill-tests --ai`. This story standardizes that pattern across all applicable commands.

### User Story

> As a developer using the agent CLI,
> I want all `--ai` commands to behave consistently,
> so that I always know what to expect: preview first, then confirm, with `--write` for CI and `--dry-run` for preview-only.

### Commands In Scope

| # | Command | File | Current `--ai` Behavior |
|---|---------|------|------------------------|
| 1 | `pr` | `workflow.py:37` | Generates PR body summary |
| 2 | `commit` | `workflow.py:147` | Infers story + generates commit message |
| 3 | `journey new` | `journey.py:79` | Generates journey content from description |
| 4 | `preflight` | `check.py:284` | AI-powered governance review |
| 5 | `impact` | `check.py:1115` | AI-powered impact analysis |
| 6 | `new-runbook` | `plan.py:31` | AI generation |
| 7 | `new-story` | `story.py:32` | AI generation |

### Scope Determination

Not all commands benefit from interactive confirm. The pattern is most valuable for commands that **generate files or content the user should review before persisting**:

- **Apply interactive confirm**: `new-story`, `new-runbook`, `journey new`, `pr`, `commit`
- **Keep as-is**: `preflight`, `impact` (these are read-only analysis tools — their output IS the deliverable)

## Acceptance Criteria

- [ ] **AC-1**: All applicable `--ai` commands follow the same 3-mode pattern:
  - `--ai` → generate → Rich preview → `Write? [y/N]` interactive confirm
  - `--ai --write` → batch write, no prompts (CI/automation mode)
  - `--ai --dry-run` → preview only, no prompts, no writes
- [ ] **AC-2**: Shared `_ai_confirm_write(content, target_path, ...)` utility function in a common module (e.g., `agent/commands/_ai_utils.py`) to avoid duplicating the Rich preview + confirm logic.
- [ ] **AC-3**: `preflight --ai` and `impact --ai` are explicitly excluded — their output is immediate analysis, not file generation.
- [ ] **AC-4**: All commands emit structured logs with consistent fields: `command`, `ai_status` (success/fallback/skipped), `duration_s`.
- [ ] **AC-5**: `--write` without `--ai` is a no-op with a helpful warning message.
- [ ] **AC-6**: Help text for `--ai`, `--write`, and `--dry-run` is standardized across all commands.

## Non-Functional Requirements

- **Backwards Compatibility**: Existing `--ai` behavior must not break. The interactive confirm is additive.
- **Consistency**: Flag names, help text wording, and Rich panel styling must be identical across commands.
- **Testability**: The shared utility must be independently testable with mock Rich console.

## Impact Analysis

### Files Modified

| File | Change |
|------|--------|
| `commands/_ai_utils.py` | NEW — shared `_ai_confirm_write()`, `_ai_preview_panel()` |
| `commands/workflow.py` | Adopt shared utility for `pr` and `commit` |
| `commands/story.py` | Adopt shared utility for `new-story` |
| `commands/plan.py` | Adopt shared utility for `new-runbook` |
| `commands/journey.py` | Adopt shared utility for `journey new` (and `backfill-tests` from INFRA-063) |

### Risks

- **Low**: Adding `--write` / `--dry-run` flags to existing commands may confuse users if not documented.
- **Mitigation**: Update help text and `commands.md` documentation.

## Test Strategy

### Unit Tests

- [ ] Test `_ai_confirm_write()` with mocked Rich console — confirm yes / no / all / skip
- [ ] Test `--ai --write` skips prompts and writes
- [ ] Test `--ai --dry-run` previews only
- [ ] Test `--write` without `--ai` emits warning
- [ ] Test help text consistency across commands

### Integration Tests

- [ ] Run `agent new-story --ai --dry-run INFRA-TEST` → verify preview output
- [ ] Run `agent new-runbook --ai --dry-run INFRA-TEST` → verify preview output

## Dependencies

- **INFRA-063**: Introduces the pattern in `backfill-tests`. This story extracts and generalizes it.
