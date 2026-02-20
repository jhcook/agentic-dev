# INFRA-064: Standardize AI by Default and Graceful Degradation Across CLI Commands

## State

IN_PROGRESS

## Plan

### Problem Statement

The CLI currently relies on an explicit `--ai` flag to leverage AI capabilities (like generating runbooks or performing preflight analysis). This requires users to constantly opt-in, increasing friction. Furthermore, when offline (e.g., on a flight), users face inconsistent UX and crashes if AI requests fail.

We need to transition to an "AI by Default" paradigm where commands use AI automatically, governed by an `--offline` (or `--no-ai`) opt-out flag. Crucially, when the AI is unreachable, the system must gracefully degrade—either by falling back to standard manual workflows (like opening `$EDITOR`) or exiting cleanly with a friendly error, rather than throwing tracebacks. We must also preserve a consistent generate → preview → confirm pattern for AI-generated artifacts to prevent unexpected writes.

### User Story

> As a developer using the agent CLI,
> I want AI features to be the default behavior so I don't have to remember to add `--ai`,
> and I want the CLI to gracefully switch to offline mode or fail cleanly when I don't have internet access,
> so that I can seamlessly work on flights or in disconnected environments and still retain control over what gets written to disk.

### Commands In Scope

| # | Command | File | Current Behavior |
|---|---------|------|------------------------|
| 1 | `pr` | `workflow.py:37` | Generates PR body summary |
| 2 | `commit` | `workflow.py:147` | Infers story + generates commit message |
| 3 | `journey new` | `journey.py:79` | Generates journey content from description |
| 4 | `preflight` | `check.py:284` | AI-powered governance review |
| 5 | `impact` | `check.py:1115` | AI-powered impact analysis |
| 6 | `new-runbook` | `plan.py:31` | AI generation |
| 7 | `new-story` | `story.py:32` | AI generation |

### Scope Determination

Not all commands degrade the same way when offline:

- **AI by Default + Interactive Confirm**: `new-story`, `new-runbook`, `journey new`, `pr`, `commit`. If offline, these commands should quietly fall back to generating empty boilerplate and opening `$EDITOR`.
- **AI by Default + Read-Only Output**: `preflight`, `impact`. These are entirely dependent on AI. If offline, they should print a clear, friendly error (e.g., "Cannot reach AI provider. Skipping AI analysis...") and exit smoothly.

## Acceptance Criteria

- [ ] **AC-1**: All applicable CLI commands drop the `--ai` flag and attempt to use AI by default.
- [ ] **AC-2**: An `--offline` (or `--no-ai`) flag is globally introduced to bypass AI explicitly.
- [ ] **AC-3**: Graceful Degradation is implemented. On connection timeout or error, generative workflows (`commit`, `new-story`, etc.) fall back to manual input in `$EDITOR`. Analysis commands (`preflight`, `impact`) print a user-friendly error and exit cleanly.
- [ ] **AC-4**: File-generating commands retain the 3-mode confirm pattern: AI generation → Rich preview → `Write? [y/N]` interactive confirm. `--write` executes a batch write (CI mode), and `--dry-run` previews without writing.
- [ ] **AC-5**: Shared `_ai_confirm_write(content, target_path, ...)` utility function is introduced in a common module (e.g., `agent/commands/_ai_utils.py`) to handle preview and confirm logic.
- [ ] **AC-6**: Structured logs include consistent fields: `command`, `ai_status` (success/offline/fallback_editor), and `duration_s`.
- [ ] **AC-7**: Help text for `--offline`, `--write`, and `--dry-run` is standardized across all commands.

## Non-Functional Requirements

- **Graceful Failure**: A lack of internet access should NEVER cause a Python traceback visible to the user.
- **Consistency**: Flag names, help text wording, and Rich panel styling must be consistent.

## Impact Analysis

### Files Modified

| File | Change |
|------|--------|
| `commands/_ai_utils.py` | NEW — shared `_ai_confirm_write()`, `_ai_preview_panel()`, graceful degradation handlers |
| `commands/workflow.py` | Adopt AI by default and graceful fallback for `pr` and `commit` |
| `commands/story.py` | Adopt AI by default and graceful fallback for `new-story` |
| `commands/plan.py` | Adopt AI by default and graceful fallback for `new-runbook` |
| `commands/journey.py` | Adopt AI by default and graceful fallback for `journey new` |
| `commands/check.py` | Adopt AI by default and graceful failure for `preflight` and `impact` |

### Risks

- **Medium**: Many existing user journeys and CI scripts rely on the explicit `--ai` flag. Removing `--ai` might break automated scripts that check for flag validation, and changing default behavior might surprise users who are used to manual entry.
- **Mitigation**: Update all user journeys in the codebase to remove the `--ai` flag and use `--offline` where manual testing is intended. Clearly document the change in `CHANGELOG.md` and `README.md`. Keep `--ai` as a deprecated, ignored flag temporarily if needed to avoid breaking CI.

## Linked Journeys

- JRN-013: Fallback and CLI Integration Tests

## Test Strategy

### Unit Tests

- [ ] Test `--offline` explicitly bypasses AI generation and calls standard behavior.
- [ ] Test network failure triggers `$EDITOR` fallback for generative commands.
- [ ] Test network failure triggers clean exit for `preflight`/`impact`.
- [ ] Test `_ai_confirm_write()` with yes / no / all / skip.

### Integration Tests

- [ ] Run `agent new-story --offline INFRA-TEST` → verify it skips AI and opens editor.
- [ ] Run `agent preflight` with network disabled → verify clean error without traceback.

## Impact Analysis Summary

- Components touched: CLI Sub-commands (`workflow.py`, `journey.py`, `plan.py`, `story.py`, `check.py`).
- Workflows affected: PR, Commit, New Journey, New Plan, New Story, Preflight, Impact.
- Risks identified: Automated scripts relying on `--ai` fail. Fallback to `typer.edit()` may stall headless CI if not bypassed via `--yes`.

## Rollback Plan

Revert the PR containing the modifications to the CLI arguments and return to the explicit `--ai` flag setup.
