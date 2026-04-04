# INFRA-179: Public Symbol Rename Detection

## Overview
This gate ensures that when the AI renames or removes a public class or function, all consumers in the codebase are updated within the same runbook. This prevents breakage during generation cycles where the AI might modify a definition but fail to update all call sites.

## AST Diffing Logic
The check parses code blocks into Abstract Syntax Trees (ASTs) to reliably identify definitions:
- **Target Nodes**: `ast.ClassDef`, `ast.FunctionDef`, and `ast.AsyncFunctionDef`.
- **Public Surface**: Only symbols without a leading underscore (e.g., `TaskExecutor`, not `_helper`) are tracked.
- **Change Detection**: A symbol is flagged for validation if it exists in the `SEARCH` block of a `[MODIFY]` instruction but is absent or renamed in the corresponding `REPLACE` block.

## Multi-Pass Validation Strategy
Because a runbook may split a large refactor across multiple files, a simple file-by-file check is insufficient. The gate uses a two-pass approach:

1.  **Index Pass**: The gate pre-scans every `[MODIFY]` and `[NEW]` block in the proposed runbook content. It builds a global `rename_map` of every public symbol being changed.
2.  **Orphan Detection Pass**: For every changed symbol identified in Pass 1:
    - The gate verifies if the symbol has consumers in the wider codebase using a restricted `grep -r` (limited to `src/` and `tests/`).
    - If consumers exist, it verifies that those specific files are also included in the runbook's modification list.
    - If consumers exist in the codebase but are missing from the runbook, the gate fails.

## Performance Considerations
To maintain gate performance, the `grep` search is restricted to `.py` files and excludes virtual environments or cache directories. Typical execution time on the current codebase is <500ms per symbol.

## Correction Mechanism
On failure, the gate emits an `api_rename_gate_fail` event and returns a correction prompt. The prompt includes the affected symbol name, the file where it was defined, and a list of consumer files that the AI must now include in the runbook to restore system integrity.
