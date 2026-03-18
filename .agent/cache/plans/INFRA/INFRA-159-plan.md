This decomposition splits INFRA-159 into three manageable child stories. The work is divided into a foundation layer (parsing/validation), an orchestration layer (the retry loop in the command), and an observability/hardening layer.

### Decomposition Plan

1.  **INFRA-159.1: S/R Validation Utilities and Parser Exposure**
    *   Expose or refactor S/R block parsing from the implementation logic so it can be used during generation.
    *   Create a standalone validation utility that checks parsed blocks against the filesystem.
    *   Handle AC-1, AC-5, and AC-6.
2.  **INFRA-159.2: Self-Healing Runbook Generation Loop**
    *   Modify `agent new-runbook` to intercept the AI response.
    *   Implement the correction prompt and the 2-retry loop logic.
    *   Handle AC-2, AC-3, and AC-4.
3.  **INFRA-159.3: Observability, Atomicity, and Hardening**
    *   Implement structured logging for the validation process.
    *   Add the `--force` override and final atomicity checks (writing to disk).
    *   Comprehensive negative testing.
    *   Handle AC-7 and NFRs.

---

### INFRA-159.1: S/R Validation Utilities and Parser Exposure
**Ref**: `INFRA-159.1`
**Scope**: ≤ 250 LOC
**Description**:
Expose the internal S/R block parsing logic from `agent/core/implement/parser.py` and create a validation utility in `agent/commands/utils.py`. This utility must identify `[MODIFY]` blocks, extract their `<<<SEARCH` content, and verify it against the local file system.

**Acceptance Criteria**:
- [ ] Refactor `agent/core/implement/parser.py` to allow parsing a runbook string into a list of block objects without executing them.
- [ ] Implement `validate_sr_blocks(runbook_content: str, base_dir: Path) -> List[ValidationFailure]` in `agent/commands/utils.py`.
- [ ] Validation logic ignores `[NEW]` blocks (AC-5).
- [ ] Validation logic returns a failure immediately if a `[MODIFY]` block targets a non-existent file (AC-6).
- [ ] Validation logic performs a verbatim string match (normalizing only trailing whitespace) between the `<<<SEARCH` block and the target file (AC-1).

---

### INFRA-159.2: Self-Healing Runbook Generation Loop
**Ref**: `INFRA-159.2`
**Scope**: ≤ 300 LOC
**Description**:
Modify the `agent new-runbook` command to incorporate the validation check. If validation fails, the command must not write the file but instead generate a correction prompt and re-invoke the AI panel.

**Acceptance Criteria**:
- [ ] Modify `agent/commands/runbook.py` to call `validate_sr_blocks` after the AI returns a draft.
- [ ] Implement a retry loop that allows up to 2 correction attempts (AC-4).
- [ ] On mismatch, construct a correction prompt containing the target file's full content and the specific failing block (AC-3).
- [ ] If all retries fail, exit with status `1` and list the unresolvable blocks (AC-2, AC-4).
- [ ] Ensure the AI is prompted to rewrite only the problematic blocks or the full runbook as appropriate for the LLM context.

---

### INFRA-159.3: Observability, Atomicity, and Hardening
**Ref**: `INFRA-159.3`
**Scope**: ≤ 200 LOC
**Description**:
Finalize the feature with structured logging, atomicity guarantees, and a bypass flag. This includes the negative testing suite to ensure robust error handling.

**Acceptance Criteria**:
- [ ] Add structured logs to the validation loop: `sr_validation_pass`, `sr_validation_fail`, `sr_correction_attempt`, `sr_correction_success`, `sr_correction_exhausted` (AC-7).
- [ ] Ensure no file content is logged at `INFO` or higher (Security NFR).
- [ ] Implement `--force` flag to allow saving unverified runbooks (Atomicity NFR).
- [ ] Add Integration Tests:
    - [ ] Mismatch triggers retry loop and succeeds on second try.
    - [ ] Exhausted retries result in exit `1` and no file on disk.
    - [ ] Missing target file results in immediate exit `1`.
- [ ] Verify performance: ensure local matching completes in < 100ms per block.
## Copyright

Copyright 2026 Justin Cook
