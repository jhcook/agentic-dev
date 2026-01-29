# STORY-INFRA-043: Anti-Drift and Suggestion/Dry-Run Workflow

## State

ACCEPTED

## Goal Description

Implement an "Anti-Drift" rule to prevent the agent from making unsolicited code changes, introduce a "Suggestion Workflow" for proposing improvements, and enable a "Dry Run" mode to preview changes before application.

## Panel Review Findings

- **@Architect**: The strategy of using a Rule (`anti-drift.mdc`) combined with a Template Change (`runbook-template.md`) is lightweight and effective.
- **@Security**: Approved. No security impact.
- **@QA**: Low risk. Manual verification is sufficient.

## Implementation Steps

### [Governance]

#### NEW .agent/rules/anti-drift.mdc

- [x] Create the rule file forbidding "unsolicited fixes" and defining the "Suggestion Pattern".

#### NEW .agent/adrs/ADR-016-cli-output-standards.md

- [x] Create ADR formalizing that `print()` is valid for CLI interaction.

### [Workflow]

#### MODIFY .agent/templates/runbook-template.md

- [x] Insert `## Proposed Improvements (Opt-In)` section.

### [Critical Fix]

#### MODIFY agent/core/fixer.py

- [x] **Fix Data Loss Bug**: Replace unsafe `git stash` logic with file-based backups (`shutil`).
  - `apply_fix`: Backup target file -> `tempfile`. Write new content.
  - `verify_fix` (pass): Delete backup.
  - `verify_fix` (fail): Restore from backup.

### [Configuration]

#### MODIFY .agent/pyproject.toml

- [x] Update `[tool.ruff]` to ignore `T201` in `src/agent/commands`.

## Verification Plan

### Manual Verification

- [ ] **Workflow Check**: Create a dummy runbook. Verify it has the new "Opt-In" section.
- [ ] **Linter Check**: Verify `ruff` does not complain about `print` in `agent/commands`.

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated

### Testing

- [ ] Manual verification complete
