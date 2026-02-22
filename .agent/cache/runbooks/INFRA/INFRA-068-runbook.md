# INFRA-068: Align `/impact` Workflow with `env -u VIRTUAL_ENV uv run agent impact` CLI

## State

ACCEPTED

## Goal Description

Simplify the `/impact` workflow to call `env -u VIRTUAL_ENV uv run agent impact` instead of duplicating analysis logic. The CLI command already supports static dependency analysis, AI-powered risk assessment, `--update-story`, `--base`, `--json`, and `--provider` flags. The main deliverable is workflow simplification plus minor CLI output improvements.

## Linked Journeys

- JRN-057: Impact Analysis Workflow

## Panel Review Findings

- **@Architect**: The `impact()` function already exists in `check.py` (line 1210). No new module needed — just workflow + minor CLI fixes. Aligns with ADR-030 (Workflow-Calls-CLI pattern).
- **@QA**: Existing test coverage for `impact` is minimal. Add unit tests for structured output and `--update-story`. Ensure negative test (no changes → clean exit 0) is covered.
- **@Security**: The `impact()` function already scrubs sensitive data before sending to AI. No new security concerns. Ensure `--update-story` doesn't inject unsanitized AI output into story files.
- **@Product**: AC1-AC4 are already partially implemented. AC5 (workflow simplification) is the primary deliverable.
- **@Observability**: Add DEBUG-level logging for dependency graph size and AI prompt size per NFR.
- **@Docs**: Update `/impact` workflow. Update `env -u VIRTUAL_ENV uv run agent impact --help` if any flag names change.
- **@Compliance**: No GDPR/SOC2 impact.
- **@Backend**: The `impact()` function uses `get_logger` correctly. Lazy imports per ADR-025 are already in place.

## Targeted Refactors & Cleanups

- [ ] Simplify `/impact` workflow to call `env -u VIRTUAL_ENV uv run agent impact` with appropriate flags
- [ ] Improve structured output format in `impact()` (components, risks, recommendations sections)
- [ ] Add DEBUG logging for dependency graph size and AI prompt size
- [ ] Add unit tests for `env -u VIRTUAL_ENV uv run agent impact`
- [ ] Add negative test: no changes → exit 0

## Implementation Steps

### 1. Simplify the `/impact` Workflow

#### [MODIFY] .agent/workflows/impact.md

Replace the entire manual process (steps 1–7: git diff, DependencyAnalyzer, AI prompt construction, etc.) with:

```markdown
1. Run `env -u VIRTUAL_ENV uv run agent impact <STORY-ID>` for static dependency analysis.
2. Run `env -u VIRTUAL_ENV uv run agent impact <STORY-ID> --ai` for AI-powered risk assessment.
3. Run `env -u VIRTUAL_ENV uv run agent impact <STORY-ID> --ai --update-story` to inject analysis into the story file.
4. Run `env -u VIRTUAL_ENV uv run agent impact <STORY-ID> --base main` to compare against a specific branch.
```

### 2. Improve Structured Output

#### [MODIFY] .agent/src/agent/commands/check.py (impact function, ~line 1210)

- Format the static analysis output with clear sections: **Components**, **Reverse Dependencies**, **Risk Summary**
- Add `logger.debug()` calls for dependency graph size and AI prompt character count
- Ensure `--json` output includes all structured fields

### 3. Add Unit Tests

#### [NEW] .agent/tests/commands/test_impact.py

- `test_impact_no_changes` — no staged changes → warning message, exit 0
- `test_impact_static_analysis` — with changed files → structured output
- `test_impact_update_story` — `--update-story` modifies story file
- `test_impact_base_branch` — `--base main` uses correct git diff command
- `test_impact_json_output` — `--json` produces valid JSON

## Files

| File | Action | Description |
|------|--------|-------------|
| `.agent/workflows/impact.md` | MODIFY | Replace manual steps with CLI calls |
| `.agent/src/agent/commands/check.py` | MODIFY | Structured output + DEBUG logging in `impact()` |
| `.agent/tests/commands/test_impact.py` | NEW | Unit tests for `env -u VIRTUAL_ENV uv run agent impact` |
| `CHANGELOG.md` | MODIFY | Add INFRA-068 entry |

## Verification Plan

### Automated Tests

- [ ] `test_impact_no_changes` — no changes → clean exit
- [ ] `test_impact_static_analysis` — structured output format
- [ ] `test_impact_update_story` — story file modification
- [ ] `test_impact_base_branch` — correct git diff invocation
- [ ] `test_impact_json_output` — valid JSON output

### Manual Verification

- [ ] Run `env -u VIRTUAL_ENV uv run agent impact INFRA-068` and verify output
- [ ] Run `env -u VIRTUAL_ENV uv run agent impact INFRA-068 --ai --update-story` and check story file
- [ ] Verify `/impact` workflow calls CLI correctly

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated
- [ ] `/impact` workflow simplified

### Observability

- [ ] DEBUG logging for graph size and prompt size

### Testing

- [ ] Unit tests pass
- [ ] Negative test (no changes) passes
