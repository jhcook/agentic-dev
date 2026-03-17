This decomposition breaks **STORY-INFRA-147** into four focused child stories. Each is scoped to a specific layer of the system (Parser, CLI Gate, Models, or Utility) to ensure changes remain under the 400 LOC limit while maintaining logical progression.

### Plan

1. **STORY-INFRA-148: Parser Robustness & Path Escaping** (Foundation)
2. **STORY-INFRA-149: Schema Validation CLI Gate** (Integration)
3. **STORY-INFRA-150: Strict Block-Level Pydantic Rules** (Refinement)
4. **STORY-INFRA-151: Python Syntax Validation & Testing** (Safety)

---

### STORY-INFRA-148: Parser Robustness & Path Escaping
**Problem**: The current parser fails on nested markdown fences (e.g., ADRs) and corrupts paths containing underscores (e.g., `__init__.py`) when rendered as markdown bold.
**Tasks**:
- Update `parser.py` regex for header extraction to automatically unescape markdown special characters (`_`, `*`, `[`, `]`).
- Refactor code fence detection to use a greedy/non-greedy balance that prevents premature closure when encountering nested triple-backticks.
- Add a utility function to escape paths before writing them to the markdown template.
- **AC**: AC-2, AC-7.
- **LOC Estimate**: ~150 lines in `agent/core/implement/parser.py`.

### STORY-INFRA-149: Schema Validation CLI Gate
**Problem**: Runbooks are written to disk even if they are structurally invalid, causing failures only during the `implement` phase.
**Tasks**:
- Modify `agent/commands/runbook.py` (`new-runbook` command) to call `validate_runbook_schema()` on the AI-generated string before I/O.
- Modify `agent/commands/panel.py` (`--apply` logic) to run the same validation gate.
- Implement a "Validation Error Formatter" that converts Pydantic `ValidationError` objects into human-readable CLI output with line numbers and step indices.
- Ensure the command exits with non-zero status on validation failure.
- **AC**: AC-1, AC-8.
- **LOC Estimate**: ~120 lines in `agent/commands/`.

### STORY-INFRA-150: Strict Block-Level Pydantic Rules
**Problem**: The Pydantic models allow "technically valid" but "semantically empty" blocks (e.g., a `[MODIFY]` block with no Search/Replace pairs).
**Tasks**:
- Update `SearchReplaceBlock` in `models.py` with `min_length=1` and whitespace stripping for `search` and `replace`.
- Add a root validator to `ModifyBlock` to ensure the `blocks` list is not empty (catching cases where the parser found the header but no S/R markers).
- Add `min_length=5` to `DeleteBlock.rationale`.
- Update `parser.py` to raise specific `ParsingError` when headers are found without required content (e.g., a `[NEW]` header without a following code fence).
- **AC**: AC-3, AC-4, AC-5.
- **LOC Estimate**: ~200 lines across `models.py` and `parser.py`.

### STORY-INFRA-151: Python Syntax Validation & Testing
**Problem**: Runbooks can generate Python code with syntax errors that pass schema validation but fail execution.
**Tasks**:
- Implement a syntax check utility using `ast.parse()` for any `[NEW]` block targeting a `.py` file.
- Integrate this utility into the validation pipeline as a non-blocking warning (log to stderr).
- Create a comprehensive negative test suite in `tests/test_runbook_validation.py` covering:
  - Missing code blocks in `[NEW]`.
  - Empty S/R in `[MODIFY]`.
  - Malformed paths.
  - Missing "Implementation Steps" section.
- **AC**: AC-6, Negative Test requirements.
- **LOC Estimate**: ~250 lines (primarily tests and utility).
