This plan decomposes INFRA-181 into four discrete child stories. The strategy is to first establish the data contracts and assembly logic, then migrate the prompts, followed by hardening the error handling, and finally cleaning up legacy code.

### Architectural Overview
The core change shifts the LLM's responsibility from generating complex Markdown syntax to generating a structured JSON array. Python then handles the "templating" of this JSON into the existing `<<<SEARCH/===/>>>` format.

---

## Plan

1. **INFRA-181-S1: Runbook JSON Schema and Assembler**
   - Define the Pydantic models for structured output.
   - Implement the Python logic that converts JSON objects into the legacy Search/Replace Markdown format.
2. **INFRA-181-S2: Phase 2 Prompt Migration and Integration**
   - Update Phase 2 prompts in the generation pipeline to request JSON.
   - Integrate the assembler into the main generation flow.
3. **INFRA-181-S3: Schema Validation and Structured Retries**
   - Implement Pydantic validation on LLM responses.
   - Replace existing markdown-based retry logic with JSON-specific correction loops and structured logging.
4. **INFRA-181-S4: Post-Processor Cleanup and Legacy Toggle**
   - Remove obsolete regex-based fixers (fence rebalancers, heading fixers).
   - Implement the `RUNBOOK_GENERATION_LEGACY` environment variable toggle for emergency rollbacks.

---

## Child Stories

### INFRA-181-S1: Runbook JSON Schema and Assembler
**Status: TODO**
Implement the data models and the transformation logic that turns JSON fields into the exact Markdown format required by downstream tools.

**Impact Analysis:**
- `.agent/src/agent/commands/runbook_generation.py`: Add `_assemble_block_from_json` helper function.
- `.agent/src/agent/core/models/runbook.py`: (New File) Define `RunbookOpJson` Pydantic model with fields: `file`, `op`, `search`, `replace`, `content`.

**Acceptance Criteria:**
- `RunbookOpJson` model correctly validates the four operation types (`modify`, `new`, `delete`).
- `_assemble_block_from_json` correctly produces `#### [MODIFY]` or `#### [NEW]` headers based on the `op` field.
- `_assemble_block_from_json` correctly wraps `search` and `replace` fields in `<<<SEARCH`, `===`, and `>>>` delimiters.
- Assembler handles stripping redundant markdown fences (triple backticks) if the LLM accidentally includes them inside the JSON string values.

---

### INFRA-181-S2: Phase 2 Prompt Migration and Integration
**Status: TODO**
Rewrite the Phase 2 prompts to instruct the model to output a JSON array instead of interleaved Markdown. Connect the output of the LLM to the assembler from S1.

**Impact Analysis:**
- `.agent/src/agent/commands/runbook_generation.py`: Rewrite prompt templates for Phase 2; update the generation loop to pass output through the JSON parser.

**Acceptance Criteria:**
- Phase 2 prompts no longer contain instructions regarding `<<<SEARCH`, `===`, `>>>`, or `#### [MODIFY]`.
- Prompt explicitly requests a JSON array of `RunbookOpJson` objects.
- The generation loop correctly routes the raw LLM response to the JSON parser and then to the assembler.
- Runbooks generated through this flow are still accepted by `agent implement`.

---

### INFRA-181-S3: Schema Validation and Structured Retries
**Status: TODO**
Add robustness to the generation pipeline by validating JSON against the schema and implementing retries for malformed JSON or missing fields.

**Impact Analysis:**
- `.agent/src/agent/commands/runbook_generation.py`: Implement the retry loop logic and schema validation check.
- `.agent/src/agent/commands/runbook_generation.py`: Emit structured log `block_generated` using the logging framework.

**Acceptance Criteria:**
- Invalid JSON (e.g., missing mandatory `file` field) triggers a retry prompt that specifically asks the model to fix the JSON schema.
- Structured log `block_generated` is emitted for every successful chunk with `op_count` and `retry_count`.
- Maximum retry limit is respected (defaulting to existing retry limits in the pipeline).

---

### INFRA-181-S4: Post-Processor Cleanup and Legacy Toggle
**Status: TODO**
Remove the brittle regex fixers that are no longer needed now that delimiters are injected by Python. Add the rollback mechanism.

**Impact Analysis:**
- `.agent/src/agent/commands/runbook_generation.py`: Remove `_fix_changelog_sr_headings`, `_rebalance_fences`, and other delimiter-related post-processors.
- `.agent/src/agent/commands/runbook_generation.py`: Wrap new logic in a conditional check for `RUNBOOK_GENERATION_LEGACY`.

**Acceptance Criteria:**
- Post-processing logic is simplified; logic previously used to "fix" model-generated delimiters is deleted.
- Setting `RUNBOOK_GENERATION_LEGACY=1` in the environment causes the tool to use the old Markdown-style prompts and parsers.
- Unit tests verify that the assembler works correctly without needing the old post-processors.