# INFRA-179: Gate 2 Extension — Public Symbol Rename Detection in [MODIFY] Blocks

## State

DRAFT

## Problem Statement

The AI has no constraint preventing it from renaming an established public class or function in a `[MODIFY]` block. INFRA-145 renamed `TaskExecutor` → `ToolExecutor` in `executor.py` with no story requirement, no runbook coverage of the rename's consumers, and no correction prompt from any gate. The rename broke `runbook_generation.py` at import time, taking down the entire `agent` CLI and requiring a manual `git restore`.

## User Story

As a developer running `agent new-runbook`, I want the pipeline to detect when a `[MODIFY]` block renames or removes a public class or function that has live consumers in the codebase, so that I receive a correction prompt if the rename is not covered by corresponding updates in the same runbook.

## Acceptance Criteria

- [ ] **AC-1**: Given a `[MODIFY]` block that removes or renames a public class/function name (detected via `ast` diff of SEARCH vs REPLACE), and that name is imported or referenced in other `.py` files in the repo, and no other block in the runbook updates those consumers — `run_generation_gates()` returns a correction prompt naming the affected symbol and files.
- [ ] **AC-2**: Given a `[MODIFY]` block that renames `Foo` → `Bar`, and another block in the same runbook updates all consumers to use `Bar`, the gate passes.
- [ ] **AC-3**: Given a `[MODIFY]` block that changes internal implementation only (no class/function name changes), the gate passes.
- [ ] **AC-4**: Private symbols (names prefixed with `_`) are excluded from the rename check.
- [ ] **AC-5**: The consumer search uses `grep -r` restricted to `.py` files in `src/` and `tests/`; it does not traverse `.venv/` or `__pycache__/`.

## Non-Functional Requirements

- Performance: `grep -r` is bounded to `src/` and `tests/`; typically <500ms on this codebase. Acceptable as a gate step.
- Observability: Emit `api_rename_gate_fail` with `symbol`, `old_name`, `new_name`, `consumers` attributes.
- Accuracy: Use `ast.parse()` on SEARCH and REPLACE blocks to extract public names; do not use regex on code.

## Linked ADRs

- ADR-046 (Observability)

## Linked Journeys

- JRN-023

## Impact Analysis Summary

Components touched: `guards.py` (new function `check_api_surface_renames`), `runbook_gates.py` (wire into Gate 2 block)
Workflows affected: `agent new-runbook` generation loop
Risks identified: False positives if the old name still appears in comments or strings — mitigated by checking import statements specifically (`from X import OldName`, `OldName(`, `OldName.`)

## Test Strategy

- Unit — `check_api_surface_renames`: rename with live consumer not covered in runbook → correction
- Unit — `check_api_surface_renames`: rename with consumer covered in sibling MODIFY block → pass
- Unit — `check_api_surface_renames`: internal implementation change only → pass
- Unit — `check_api_surface_renames`: private `_name` renamed → skipped
- Unit — `check_api_surface_renames`: rename with no consumers in codebase → pass
- Integration — `run_generation_gates` with INFRA-145-equivalent `TaskExecutor→ToolExecutor` → correction_parts non-empty

## Rollback Plan

Remove the `check_api_surface_renames` call from `run_generation_gates`. Purely additive; no state mutation.

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
