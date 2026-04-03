# INFRA-176: Gate 3.5 — Projected Syntax Validation for [MODIFY] S/R Blocks

## State

REVIEW_NEEDED

## Problem Statement

The generation-time code gate (`validate_code_block`) runs `ast.parse()` only on `[NEW]` full-file blocks. `[MODIFY]` S/R replacements are never syntax-checked on their projected result. This means the AI can produce a `[MODIFY]` block whose REPLACE content will cause a `SyntaxError` when applied — e.g. SQL DDL injected at wrong indentation — and it passes every gate cleanly. The error is only discovered at collection time when preflight runs the test suite.

## User Story

As a developer running `agent new-runbook`, I want the pipeline to detect when a `[MODIFY]` S/R replacement would produce syntactically broken Python, so that I never receive a runbook whose `--apply` will corrupt a source file.

## Acceptance Criteria

- [ ] **AC-1**: Given a `[MODIFY]` block whose REPLACE produces a `SyntaxError` when applied to the on-disk file, `run_generation_gates()` returns a correction prompt describing the exact error and location. The runbook is not accepted.
- [ ] **AC-2**: Given a `[MODIFY]` block whose REPLACE produces valid Python, the gate passes with no correction prompt.
- [ ] **AC-3**: The check only runs on `.py` files; non-Python files (`.md`, `.yaml`, `.txt`) are skipped silently.
- [ ] **AC-4**: The check operates on an in-memory copy of the file — it never writes to disk and never modifies the working tree.
- [ ] **AC-5**: If the search text is not found in the on-disk file (already caught by the S/R gate), this gate is a no-op for that block.
- [ ] **AC-6**: When `check_projected_syntax` raises a correction (i.e. the REPLACE content produces a `SyntaxError` after projection), `run_generation_gates()` appends a correction prompt instructing the AI to re-emit the complete, syntactically valid REPLACE block — identical recovery path to a SEARCH mismatch. The generation loop retries rather than hard-failing.
- [ ] **AC-7 (DEFERRED → INFRA-178)**: Undefined-name / `NameError` detection requires full AST scope analysis (walking the parse tree to resolve imports and in-scope definitions). This is substantially more complex than `ast.parse()` SyntaxError checking and is out of scope for INFRA-176. A dedicated story (INFRA-178) will implement the scope-walking guard.

## Non-Functional Requirements

- Performance: `ast.parse()` on an in-memory string adds <2ms per file; total gate overhead must be <200ms for a typical 10-file runbook.
- Observability: Emit a structured log event `projected_syntax_gate_fail` with `file`, `error`, and `line` attributes.
- Correctness: Read the file using the same encoding handling as `apply_chunk` (UTF-8).

## Linked ADRs

- ADR-046 (Observability — structured logging)

## Linked Journeys

- JRN-023 (Voice logic orchestration — broke due to session.py corruption)

## Impact Analysis Summary

New modules introduced:
- `agent.utils.path_utils` — new shared utility providing `validate_path_integrity`, moved out of the `commands` layer so both `core` and `commands` can import it without an architectural layering violation.
- `agent.utils.rollback_infra_176` — rollback script for safely removing Gate 3.5 integration if needed.

Modified modules:
- `agent.core.implement.guards` — new function `check_projected_syntax` (AC-1 to AC-6); updated top-level import to use `agent.utils.path_utils`; `root_dir` argument added to avoid coupling to global config state.
- `agent.commands.runbook_gates` — wires `check_projected_syntax` into `run_generation_gates` after Gate 3, wrapped in an OTel span (`validate_projected_syntax_gate`); passes `root_dir=config.repo_root`.
- `agent.commands.gates` — `validate_path_integrity` definition replaced with a re-export from `agent.utils.path_utils` for backward compatibility.
- `agent.utils.validation_formatter` — `format_projected_syntax_error` helper used by `check_projected_syntax` to standardise correction-prompt output.

Workflows affected: `agent new-runbook` (gate fires during generation loop)
Risks identified: False negative if search text matches multiple locations — mitigated by replacing only the first occurrence (same as apply_chunk)

## Test Strategy

- Unit — `check_projected_syntax`: SQL DDL injected at wrong indent → SyntaxError caught
- Unit — `check_projected_syntax`: Valid S/R replacement → gate passes
- Unit — `check_projected_syntax`: Non-Python file → gate skipped
- Unit — `check_projected_syntax`: Search text not found → gate is no-op
- Integration — `run_generation_gates` with a corrupted MODIFY block → correction_parts non-empty
- Integration — `run_generation_gates` with a REPLACE that has an unclosed parenthesis → correction prompt contains syntax error description; loop retries (AC-6)
- Regression — verify `new-runbook INFRA-176` no longer exits with code 1 due to `sr_replace_syntax_fail`

## Rollback Plan

Remove the `check_projected_syntax` call from `run_generation_gates`. The function is an additive check with no side effects; removal restores prior behavior exactly.

## Copyright

Copyright 2026 Justin Cook

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
