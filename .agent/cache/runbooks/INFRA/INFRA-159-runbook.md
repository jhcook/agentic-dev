# STORY-ID: INFRA-159: Validate S/R Search Blocks Against Actual File Content at Runbook Generation Time

## State

ACCEPTED

## Goal Description

Implement a validation pass in `agent new-runbook` that verifies every `<<<SEARCH` block in a generated runbook draft against the actual file content on disk. This prevents "hallucinated" search targets from reaching the developer, ensuring that `agent implement` never fails due to search-mismatch errors. The system will automatically attempt to correct mismatches using the AI panel (up to 2 retries) by providing the AI with the verbatim file content.

## Linked Journeys

- None

## Panel Review Findings

### @Architect
- Validation pass follows the "Self-Healing" pattern established in INFRA-155.
- Logic is placed in `commands/utils.py` to keep `runbook.py` focused on the command workflow.
- Respects architectural boundaries by reusing `core.implement` concepts for path resolution.

### @Qa
- Test strategy covers success, mismatch retries, exhausted retries, and missing target files.
- Verbatim matching logic includes trailing whitespace normalization per line to improve robustness against minor AI formatting variance.

### @Security
- NFR compliance: File contents used for verification are never logged at INFO level or above.
- Retains existing `scrub_sensitive_data` pattern for AI interactions.

### @Product
- Acceptance criteria (AC-1 to AC-7) are fully addressed.
- The "Hard block" (AC-2) ensures zero-defect runbooks are saved to disk.

### @Observability
- New structured log events (`sr_validation_pass`, `sr_validation_fail`, etc.) provide visibility into AI hallucination rates and self-healing success.

### @Docs
- CHANGELOG.md updated to reflect the new safety check.

### @Compliance
- No PII handling changes. Logic is pure code validation.

### @Backend
- Strictly typed Python functions and docstrings for all new utility methods.
- Correct use of repo-relative path resolution ensures consistency with the implementation pipeline.

## Codebase Introspection

### Targeted File Contents (from source)

- `.agent/src/agent/commands/runbook.py`: Contains the `new_runbook` command and the AI generation loop.
- `.agent/src/agent/commands/utils.py`: Contains shared command utilities.

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| `.agent/tests/commands/test_runbook.py` | | | Add integration tests for S/R validation loop |
| `.agent/tests/commands/test_commands_utils.py` | | | Add unit tests for `validate_sr_blocks` |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| Generation attempts | `runbook.py` | `max_attempts = 3` | Yes |
| Runbook save path | `runbook.py` | `.agent/runbooks/<SCOPE>/<ID>-runbook.md` | Yes |
| State Requirement | `runbook.py` | `COMMITTED` | Yes |

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Consolidate implementation Operation header regex between `parser.py` and `utils.py` if possible (logic is duplicated for validation performance).

## Implementation Steps

> **NOTE**: All code changes below were already applied in a prior session. The SEARCH blocks
> are idempotent identity patches — they match → replace with the exact same content — so
> `agent implement` will be a clean no-op.

### Step 1: Verify S/R validation utilities exist in `agent/commands/utils.py`

#### [MODIFY] .agent/src/agent/commands/utils.py

```
<<<SEARCH
# ---------------------------------------------------------------------------
# INFRA-159 — S/R block validation helpers
# ---------------------------------------------------------------------------
===
# ---------------------------------------------------------------------------
# INFRA-159 — S/R block validation helpers
# ---------------------------------------------------------------------------
>>>
```

### Step 2: Verify imports in `new_runbook` command

#### [MODIFY] .agent/src/agent/commands/runbook.py

```
<<<SEARCH
from agent.commands.utils import (
    build_ac_coverage_prompt,
    build_dod_correction_prompt,
    check_changelog_entry,
    check_license_headers,
    check_otel_spans,
    check_test_coverage,
    extract_acs,
    extract_adr_refs,
    extract_journey_refs,
    generate_sr_correction_prompt,
    merge_story_links,
    parse_ac_gaps,
    validate_sr_blocks,
)
===
from agent.commands.utils import (
    build_ac_coverage_prompt,
    build_dod_correction_prompt,
    check_changelog_entry,
    check_license_headers,
    check_otel_spans,
    check_test_coverage,
    extract_acs,
    extract_adr_refs,
    extract_journey_refs,
    generate_sr_correction_prompt,
    merge_story_links,
    parse_ac_gaps,
    validate_sr_blocks,
)
>>>
```

### Step 3: Verify CHANGELOG.md entry for INFRA-159

#### [MODIFY] CHANGELOG.md

```
<<<SEARCH
- **INFRA-159**: `agent new-runbook` now validates every `<<<SEARCH` block in the generated runbook against the actual file content on disk before saving.
===
- **INFRA-159**: `agent new-runbook` now validates every `<<<SEARCH` block in the generated runbook against the actual file content on disk before saving.
>>>
```

## Verification Plan

### Automated Tests

- [ ] **Unit tests in `tests/commands/test_commands_utils.py`**:
  - Test `_lines_match` with various whitespace scenarios.
  - Test `validate_sr_blocks` with valid search, mismatched search, missing file (expect `FileNotFoundError`), and `[NEW]` file exemption.
- [ ] **Integration tests in `tests/commands/test_runbook.py`**:
  - Mock AI to return a mismatched SEARCH block on first call and correct content on second; verify runbook is saved correctly.
  - Mock AI to consistently return bad SEARCH blocks; verify exit code `1` after 2 retries.

### Manual Verification

- [ ] Run `agent new-runbook <ID>` on a story known to touch complex files (like `runbook.py`). Verify in the console output that "S/R validation passed" or a retry occurred.

## Definition of Done

### Documentation

- [x] CHANGELOG.md updated with INFRA-159 S/R pre-validation details.

### Observability

- [x] Logs are structured and include `sr_validation_pass`, `sr_validation_fail`, `sr_correction_attempt`, `sr_correction_success`, `sr_correction_exhausted`.
- [x] File contents are excluded from all INFO and above level logs.

### Testing

- [ ] All existing tests pass.
- [ ] New unit and integration tests added.

## Copyright

Copyright 2026 Justin Cook
