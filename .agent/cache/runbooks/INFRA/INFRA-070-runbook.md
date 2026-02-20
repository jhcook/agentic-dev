# INFRA-070: Align `/pr` Workflow with `agent pr` CLI

## State

ACCEPTED

## Goal Description

Simplify the `/pr` workflow to call `agent pr` instead of duplicating preflight/body/gh logic. The CLI already handles preflight integration, auto-generated body/title, `gh pr create`, AI summary, and `gh` not-found error. Remaining work: add `--skip-preflight` flag, scrub body in non-AI mode, and simplify the workflow.

## Linked Journeys

- JRN-059: PR Creation Workflow

## Panel Review Findings

- **@Architect**: The `pr()` function already exists in `workflow.py:30-140` with most ACs complete. This follows the ADR-030 Workflow-Calls-CLI pattern established in INFRA-068/069.
- **@QA**: No existing tests for `agent pr`. Add unit tests for title formatting, body generation, skip-preflight flag, and gh-not-found error.
- **@Security**: AC5 (body scrubbing) only applies in AI mode currently. Must also scrub the base body template to prevent leaking story content that might contain sensitive data. The `--skip-preflight` flag must be audit-logged per AC6.
- **@Product**: AC1-AC5 mostly satisfied. AC6 (`--skip-preflight`) and AC7 (workflow simplification) are the primary deliverables.
- **@Observability**: Add timestamped audit logging for `--skip-preflight` usage per AC6.
- **@Docs**: Update `/pr` workflow. Ensure `agent pr --help` is accurate.
- **@Compliance**: `--skip-preflight` must log timestamp and user intent for SOC2 audit trail.

## Targeted Refactors & Cleanups

- [ ] Add `--skip-preflight` flag with audit logging (AC6)
- [ ] Scrub body in non-AI mode too (AC5 gap)
- [ ] Simplify `/pr` workflow to CLI-first instructions (AC7)
- [ ] Add unit tests for `agent pr`
- [ ] Update CHANGELOG

## Implementation Steps

### 1. Add `--skip-preflight` Flag

#### [MODIFY] .agent/src/agent/commands/workflow.py (pr function, ~line 30)

- Add `skip_preflight: bool = typer.Option(False, "--skip-preflight", help="Skip preflight checks (audit-logged).")`
- When set, skip the `preflight()` call, log a warning with timestamp:

  ```python
  if skip_preflight:
      import time
      console.print(f"[yellow]⚠️  Preflight SKIPPED at {time.strftime('%Y-%m-%dT%H:%M:%S')} (--skip-preflight)[/yellow]")
  ```

- Update body template to show `⚠️ Preflight Skipped` instead of `✅ Preflight Passed`

### 2. Scrub Body in Non-AI Mode

#### [MODIFY] .agent/src/agent/commands/workflow.py (pr function)

- Apply `scrub_sensitive_data()` to the final `body` before passing to `gh pr create`, not just the AI diff
- Import already exists in the AI branch; move it to top-level of function

### 3. Simplify the `/pr` Workflow

#### [MODIFY] .agent/workflows/pr.md

Replace the 73-line manual process with:

```markdown
1. Run `agent pr --story <STORY-ID>` to create a PR with preflight checks.
2. Run `agent pr --story <STORY-ID> --ai` for AI-generated PR summary.
3. Run `agent pr --story <STORY-ID> --web` to open in browser.
4. Run `agent pr --story <STORY-ID> --draft` for draft PR.
5. Run `agent pr --story <STORY-ID> --skip-preflight` to skip preflight (audit-logged).
```

### 4. Add Unit Tests

#### [NEW] .agent/tests/commands/test_pr.py

- `test_pr_title_format` — title includes `[STORY-ID]`
- `test_pr_skip_preflight_logs_warning` — skipped → warning with timestamp
- `test_pr_gh_not_found` — `FileNotFoundError` → clear error, exit 1
- `test_pr_body_scrubbing` — body passed through `scrub_sensitive_data()`

## Files

| File | Action | Description |
|------|--------|-------------|
| `.agent/src/agent/commands/workflow.py` | MODIFY | `--skip-preflight` flag + body scrubbing |
| `.agent/workflows/pr.md` | MODIFY | Replace manual process with CLI calls |
| `.agent/tests/commands/test_pr.py` | NEW | Unit tests for `agent pr` |
| `CHANGELOG.md` | MODIFY | Add INFRA-070 entry |

## Verification Plan

### Automated Tests

- [ ] `test_pr_title_format` — title formatting
- [ ] `test_pr_skip_preflight_logs_warning` — audit logging
- [ ] `test_pr_gh_not_found` — graceful error
- [ ] `test_pr_body_scrubbing` — sensitive data removed

### Manual Verification

- [ ] Run `agent pr --story INFRA-070 --skip-preflight` and check audit warning
- [ ] Verify `/pr` workflow calls CLI correctly

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated
- [ ] `/pr` workflow simplified

### Testing

- [ ] Unit tests pass
- [ ] Existing tests unaffected
