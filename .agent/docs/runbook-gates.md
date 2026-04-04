# Runbook Generation Gates

This document describes the automated safety gates enforced during the runbook generation process to ensure code integrity and prevent breaking changes.

## Public Symbol Rename Detection

**Objective**
To prevent breaking changes caused by renaming or removing public functions and classes without updating their consumers. This gate ensures that the AI framework maintains the public contract of the codebase as defined in Rule 303.

**Inclusion and Exclusion Criteria**

**Public Symbols (Included):**
- Any function definition (`def`) or class definition (`class`) that does **not** start with a leading underscore.
- Example: `class TaskExecutor:` or `def execute_task():` are considered public and will be tracked.

**Private Symbols (Excluded):**
- Any symbol prefixed with a leading underscore (`_`) is considered internal to its module or package.
- Example: `def _internal_helper():` will be ignored by this gate, allowing for internal refactors without explicit consumer tracking.

**Technical Logic**
1. **AST Analysis**: The gate uses `ast.parse()` to compare the `SEARCH` block and the `REPLACE` block of every `[MODIFY]` instruction in the runbook.
2. **Diffing**: It identifies public symbols present in the `SEARCH` section that are missing or renamed in the `REPLACE` section.
3. **Consumer Search**: For every detected rename/removal, the system performs a recursive `grep` search through `src/` and `tests/` to find live references to the old symbol name.
4. **Runbook Coverage**: The gate verifies if every file containing a reference is also included in the current runbook with its own `[MODIFY]` block updating the reference.

**Resolving Correction Prompts**
If a rename is detected but consumers are orphaned, the generation loop will issue a correction prompt.

**Example Correction Prompt:**
> Public symbol 'TaskExecutor' was renamed to 'ToolExecutor' in 'src/executor.py', but references were found in the following files that are not updated in this runbook: 'src/main.py', 'tests/test_executor.py'. Please update all consumers.

**Steps to Resolve:**
- **Option A (Update Consumers)**: Add `[MODIFY]` blocks for the orphaned files (`src/main.py`, etc.) to the runbook that update the symbol name to the new value.
- **Option B (Revert Rename)**: If the rename was not intended by the story requirements, revert the change in the original file's `REPLACE` block to match the `SEARCH` block name.
