# INFRA-178: Gate 2 Extension — Test Import Resolution for [NEW] Test Files

## State

COMMITTED

## Problem Statement

The DoD gate checks that every `[NEW]` implementation file has a paired `[NEW]` test file, but it never checks whether the test file's imports resolve. INFRA-145 generated test files that imported `ToolRegistry` and `AgentExecutor` — symbols the runbook never implemented. These files passed every generation-time gate, were checked into staging, and then caused 12 collection errors in `agent preflight`.

## User Story

As a developer running `agent new-runbook`, I want the pipeline to verify that every `[NEW]` test file's top-level imports resolve to either an existing on-disk symbol or a symbol defined in another block of the same runbook, so that generated test files don't fail at collection time.

## Acceptance Criteria

- [ ] **AC-1**: Given a `[NEW]` test file block that imports `from agent.core.foo import Bar`, where `Bar` does not exist in `agent/core/foo.py` on disk and is not defined in any other `[NEW]`/`[MODIFY]` block in the runbook, `run_generation_gates()` returns a correction prompt naming the unresolvable import.
- [ ] **AC-2**: Given a `[NEW]` test file that imports a symbol defined in another `[NEW]` block in the same runbook, the gate passes.
- [ ] **AC-3**: Given a `[NEW]` test file that imports only from the stdlib (`os`, `pathlib`, `typing`, etc.) or installed third-party packages present in the venv, the gate passes.
- [ ] **AC-4**: Imports inside `if TYPE_CHECKING:` blocks are excluded from resolution checks.
- [ ] **AC-5**: The check only applies to files matching `tests/**/*.py` naming pattern; non-test new files are not subject to this gate.

## Non-Functional Requirements

- Observability: Emit `test_import_resolution_fail` with `file`, `unresolved_symbols` attributes.
- Accuracy: Use `ast.parse()` on the `[NEW]` block content to extract imports; do not use regex.
- Performance: Symbol lookup uses an in-memory index built once per gate run from all `[NEW]`/`[MODIFY]` blocks.

## Dependencies

- **INFRA-176** (Gate 3.5: projected syntax validation) — modified both target files before this story. `guards.py` already imports `ast`, `re`, `sys`, `importlib.util` and uses `logger = logging.getLogger(__name__)` (NOT `get_logger`). `runbook_gates.py` already imports `from agent.utils.validation_formatter import format_runbook_errors` on the line after `from agent.core.implement.orchestrator import validate_runbook_schema`.

## Linked ADRs

- ADR-046 (Observability)

## Linked Journeys

- JRN-023

## Impact Analysis Summary

Components touched:
- `.agent/src/agent/core/implement/guards.py` — add `check_test_imports_resolvable(file_path, content, session_symbols)`. **Current anchor**: `ast`, `re`, `sys`, `importlib.util` are already imported (added by INFRA-176). `logger = logging.getLogger(__name__)` is on line 36. Add the new function after the `check_projected_syntax` function.
- `.agent/src/agent/commands/runbook_gates.py` — add `check_test_imports_resolvable` to the guards import block (currently lines 48-55, ending with `check_stub_implementations,`), add `_build_runbook_symbol_index` helper before `run_generation_gates`, and call the check inside `run_generation_gates` after Gate 3.5. **Exact insertion anchor** for the Gate 3.7 call (after Gate 3.5 span closes):
  ```
              if syntax_err:
                  correction_parts.append(syntax_err)
      syn_span.set_attribute("gate35.corrections", len(correction_parts))
  ```
  Insert Gate 3.7 block immediately after that last `syn_span.set_attribute` line. **Do NOT re-add** `from agent.utils.validation_formatter import format_runbook_errors` — already present on line 58.
- **Type contract**: `_build_runbook_symbol_index(content: str) -> Set[str]` — must return a **flat `Set[str]`** of fully-qualified symbol names (e.g. `{"check_test_imports_resolvable", "MyClass"}`), NOT a `Dict`. `check_test_imports_resolvable` receives it as `session_symbols: Set[str]` and does `symbol_name in session_symbols`.
- `.agent/src/agent/utils/rollback_infra_178.py` — new rollback script
- `.agent/tests/unit/test_guards_import_resolution.py` — unit tests (consistent with INFRA-176 test layout under `tests/unit/`)
- `.agent/tests/commands/test_runbook_gates_import_resolution.py` — integration test for `run_generation_gates` with ghost import

Workflows affected: `agent new-runbook` generation loop
Risks identified: False positives for dynamic imports or `importlib` usage — mitigated by only checking static top-level `import`/`from...import` statements

## Test Strategy

- Unit — `check_test_imports_resolvable`: test imports non-existent symbol → correction
- Unit — `check_test_imports_resolvable`: test imports symbol defined in sibling `[NEW]` block → pass
- Unit — `check_test_imports_resolvable`: test imports `os`, `pathlib` → pass (stdlib)
- Unit — `check_test_imports_resolvable`: import inside `TYPE_CHECKING` block → skipped
- Unit — `check_test_imports_resolvable`: non-test `[NEW]` file → gate is no-op
- Integration — `run_generation_gates` with a test file importing ghost symbol → correction_parts non-empty

## Rollback Plan

Remove the `check_test_imports_resolvable` call from `run_generation_gates`. Purely additive; no state mutation.

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
