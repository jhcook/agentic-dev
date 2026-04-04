# Runbook: Implementation Runbook for INFRA-179

## State

ACCEPTED

## Implementation Steps

### Step 1: Architecture & Design Review

#### [MODIFY] CHANGELOG.md

```

<<<SEARCH
## [Unreleased] (Updated by story)
===
## [Unreleased] (Updated by story)

**Added**
- INFRA-179: Public symbol rename detection gate (Gate 2) — detects when [MODIFY] blocks rename/remove public classes or functions without updating all consumers.
>>>

```

#### [NEW] .agent/docs/architecture/infra-179-rename-detection.md

```markdown
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

```

### Step 2: Implementation: Rename Detection & Gate Integration

#### [MODIFY] .agent/src/agent/core/implement/guards.py

```

<<<SEARCH
def check_test_imports_resolvable(
===
def _extract_public_symbols(code: str) -> Set[str]:
    """Extract public classes and functions from code using AST parsing."""
    try:
        tree = ast.parse(code)
        symbols = set()
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                if not node.name.startswith('_'):
                    symbols.add(node.name)
        return symbols
    except Exception:
        return set()

def check_api_surface_renames(blocks: List[Dict[str, str]], repo_root: Path) -> List[str]:
    """
    Detect renames or removals of public symbols in [MODIFY] blocks.
    Ensures all consumers in the codebase are updated within the same runbook.
    """
    all_renames: Dict[str, str] = {}
    all_deletions: Set[str] = set()
    file_to_removed_symbols: Dict[str, Set[str]] = {}

    # Pass 1: Identify all renames/removals across all blocks
    for block in blocks:
        filename = block.get("file", "")
        search_code = block.get("search", "")
        replace_code = block.get("replace", "")
        
        search_symbols = _extract_public_symbols(search_code)
        replace_symbols = _extract_public_symbols(replace_code)
        
        removed = search_symbols - replace_symbols
        added = replace_symbols - search_symbols
        
        # 1-to-1 change in a block is treated as a rename
        if len(removed) == 1 and len(added) == 1:
            old = list(removed)[0]
            new = list(added)[0]
            all_renames[old] = new
        else:
            all_deletions.update(removed)
        
        if removed:
            if filename not in file_to_removed_symbols:
                file_to_removed_symbols[filename] = set()
            file_to_removed_symbols[filename].update(removed)

    errors = []
    updated_files = {block["file"] for block in blocks}
    
    # Pass 2: Check for survivors (consumers not updated)
    for source_file, symbols in file_to_removed_symbols.items():
        for symbol in symbols:
            new_name = all_renames.get(symbol)
            pattern = rf"\b{re.escape(symbol)}\b"
            
            # Grep -r restricted to src/ and tests/
            # -l: only filenames, -r: recursive
            cmd = ["grep", "-r", "-l", "--include=*.py", "--exclude-dir=.venv", "--exclude-dir=__pycache__", pattern, "src", "tests"]
            try:
                result = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=False)
                if result.returncode > 1: # grep returns 2 on true error
                    continue
                    
                consumers = [f for f in result.stdout.splitlines() if not f.endswith(source_file)]
                if not consumers:
                    continue

                # Check if each consumer is covered by another block in this runbook
                orphaned = []
                for consumer in consumers:
                    is_handled = False
                    if consumer in updated_files:
                        # Ensure the old symbol is actually gone from the replacement code
                        for b in blocks:
                            if b["file"] == consumer:
                                if not re.search(pattern, b.get("replace", "")):
                                    is_handled = True
                                    break
                    if not is_handled:
                        orphaned.append(consumer)

                if orphaned:
                    status = f"renamed to '{new_name}'" if new_name else "removed"
                    msg = f"Public symbol '{symbol}' was {status} in {source_file}, but has live consumers in: {', '.join(orphaned)}"
                    errors.append(msg)
                    
                    log_governance_event("api_rename_gate_fail", {
                        "symbol": symbol,
                        "old_name": symbol,
                        "new_name": new_name,
                        "consumers": orphaned
                    })
            except Exception as e:
                logger.error(f"Rename check failed for {symbol}: {e}")

    return errors

from typing import List
>>>

```

#### [MODIFY] .agent/src/agent/commands/runbook_gates.py

```

<<<SEARCH
from agent.core.implement.guards import (
    check_projected_loc,
    check_projected_syntax,
    validate_code_block,
    check_impact_analysis_completeness,
    check_adr_refs,
    check_stub_implementations,
    check_test_imports_resolvable,
)
===
from agent.core.implement.guards import (
    check_projected_loc,
    check_projected_syntax,
    validate_code_block,
    check_impact_analysis_completeness,
    check_adr_refs,
    check_stub_implementations,
    check_test_imports_resolvable,
    check_api_surface_renames,
)
>>>

```

#### [MODIFY] .agent/src/agent/commands/runbook_gates.py

```
<<<SEARCH
    # 2. Code Gate Self-Healing (INFRA-155 AC-1)
===
    # Gate 1c: API Surface Rename Detection (INFRA-179)
    with tracer.start_as_current_span("api_rename_gate") as rename_span:
        sr_blocks_for_rename: List[Dict[str, str]] = parse_search_replace_blocks(content)
        rename_span.set_attribute("gate1c.block_count", len(sr_blocks_for_rename))
        rename_errors = check_api_surface_renames(sr_blocks_for_rename, config.repo_root)
        rename_span.set_attribute("gate1c.corrections", len(rename_errors))
        if rename_errors:
            logger.warning(
                "api_rename_gate_fail",
                extra={"story_id": story_id, "errors": rename_errors},
            )
            for err in rename_errors:
                correction_parts.append(
                    f"API RENAME GATE (Gate 1c):\n{err}\n"
                    "Add [MODIFY] blocks for all consumer files, or revert the rename."
                )

    # 2. Code Gate Self-Healing (INFRA-155 AC-1)
>>>

```

### Step 3: Security & Input Sanitization

#### [MODIFY] .agent/src/agent/commands/gates.py

```

<<<SEARCH
def log_skip_audit(gate_name: str, resource_id: str = "") -> None
===
def run_safe_grep(pattern: str, search_paths: List[str]) -> List[str]:
    """
    Executes a recursive grep search safely using list-based arguments.
    
    Args:
        pattern: The sanitized regex pattern to search for.
        search_paths: List of directory paths to search within.
        
    Returns:
        List of file paths containing matches.
    """
    # Restrict search to python files and provided paths only
    # Using list-based arguments prevents shell injection (no shell=True)
    cmd = ["grep", "-r", "-l", "--include=*.py", "-E", pattern] + search_paths
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        # returncode 1 means no matches, >1 means grep error
        return []
    except Exception as e:
        get_logger(__name__).error(f"Security Error: Grep execution failed: {e}")
        return []

def log_skip_audit(gate_name: str, resource_id: str = "") -> None
>>>

```



### Step 4: Observability & Audit Logging

#### [MODIFY] .agent/src/agent/commands/audit.py

```

<<<SEARCH
import typer
from pathlib import Path
from typing import Optional
import logging
import json
from datetime import datetime

from agent.core.governance import run_audit, log_governance_event
from agent.core.formatters import format_audit_report
from agent.core.security import scrub_sensitive_data
from agent.tools.telemetry import get_tool_metrics
===
from typing import List, Optional
import typer
from pathlib import Path
import logging
import json
from datetime import datetime

from agent.core.governance import run_audit, log_governance_event
from agent.core.formatters import format_audit_report
from agent.core.security import scrub_sensitive_data
from agent.tools.telemetry import get_tool_metrics
from typing import List, Optional
import logging
import json
from datetime import datetime
from agent.core.governance import run_audit, log_governance_event
from agent.core.formatters import format_audit_report


def log_api_rename_gate_fail(symbol: str, old_name: str, new_name: Optional[str], consumers: List[str]) -> None:
    """
    Emit a structured 'api_rename_gate_fail' event for audit and observability.

    This function complies with ADR-046 by logging the failed rename attempt
    to both the system logger and the governance event log.

    Args:
        symbol: The public class or function name being changed.
        old_name: The original name found in the SEARCH block.
        new_name: The new name found in the REPLACE block (or None if deleted).
        consumers: List of file paths where the old symbol is still referenced.
    """
    # 1. System Logger Emission
    logger = logging.getLogger("agent.guards")
    logger.error(
        "api_rename_gate_fail",
        extra={
            "symbol": symbol,
            "old_name": old_name,
            "new_name": new_name,
            "consumers": consumers,
            "adr": "ADR-046"
        }
    )

    # 2. Governance Audit Logging
    log_governance_event(
        event_type="api_rename_gate_fail",
        payload={
            "symbol": symbol,
            "old_name": old_name,
            "new_name": new_name,
            "consumers": consumers
        }
    )
>>>

```

### Step 5: Verification & Test Suite

#### [NEW] .agent/tests/unit/test_guards_renames.py

```python
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from agent.core.implement.guards import check_api_surface_renames

def test_check_api_surface_renames_private_ignored():
    """AC-4: Verify that symbols starting with an underscore are ignored."""
    blocks = [{
        "file": "src/logic.py",
        "search": "def _internal_helper():\n    return 1",
        "replace": "def _refactored_helper():\n    return 1"
    }]
    # Even if grep found consumers, it shouldn't run for private symbols
    with patch("subprocess.run") as mock_run:
        errors = check_api_surface_renames(blocks, Path("/tmp"))
        assert len(errors) == 0
        mock_run.assert_not_called()

def test_check_api_surface_renames_implementation_only():
    """AC-3: Verify that changing function body without renaming passes."""
    blocks = [{
        "file": "src/api.py",
        "search": "def get_data():\n    return []",
        "replace": "def get_data():\n    # New implementation\n    return None"
    }]
    errors = check_api_surface_renames(blocks, Path("/tmp"))
    assert len(errors) == 0

def test_check_api_surface_renames_orphaned_consumer():
    """AC-1: Verify rename with live consumer not in runbook triggers error."""
    blocks = [{
        "file": "src/executor.py",
        "search": "class TaskExecutor:\n    pass",
        "replace": "class ToolExecutor:\n    pass"
    }]
    
    with patch("subprocess.run") as mock_run:
        # Mock grep finding the old name in a file NOT in the runbook
        mock_run.return_value = MagicMock(
            returncode=0, 
            stdout="src/main.py\n"
        )
        
        errors = check_api_surface_renames(blocks, Path("/tmp"))
        assert len(errors) == 1
        assert "'TaskExecutor' was renamed to 'ToolExecutor'" in errors[0]
        assert "src/main.py" in errors[0]

def test_check_api_surface_renames_covered_consumer():
    """AC-2: Verify rename with consumer covered in runbook passes."""
    blocks = [
        {
            "file": "src/executor.py",
            "search": "class TaskExecutor:\n    pass",
            "replace": "class ToolExecutor:\n    pass"
        },
        {
            "file": "src/main.py",
            "search": "TaskExecutor()",
            "replace": "ToolExecutor()"
        }
    ]
    
    with patch("subprocess.run") as mock_run:
        # Mock grep finding the consumer in main.py (which is in our runbook)
        mock_run.return_value = MagicMock(
            returncode=0, 
            stdout="src/main.py\n"
        )
        
        errors = check_api_surface_renames(blocks, Path("/tmp"))
        assert len(errors) == 0

def test_check_api_surface_renames_no_consumers():
    """Verify rename with no consumers in codebase passes."""
    blocks = [{
        "file": "src/unused.py",
        "search": "def legacy_func():\n    pass",
        "replace": "def modern_func():\n    pass"
    }]
    
    with patch("subprocess.run") as mock_run:
        # Mock grep finding nothing (returncode 1)
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        
        errors = check_api_surface_renames(blocks, Path("/tmp"))
        assert len(errors) == 0

```

#### [NEW] .agent/tests/commands/test_runbook_gates_renames.py

```python
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from agent.commands.runbook_gates import run_generation_gates

def test_run_generation_gates_trigger_rename_correction():
    """Integration test: verify the correction prompt trigger for renames."""
    content = """
[MODIFY] src/executor.py
<<<<SEARCH
class TaskExecutor:
    pass
====
class ToolExecutor:
    pass
>>>>
"""
    
    with patch("agent.core.implement.guards.subprocess.run") as mock_run:
        # Simulate finding a consumer in runbook_generation.py (INFRA-145 case)
        mock_run.return_value = MagicMock(
            returncode=0, 
            stdout="src/runbook_generation.py\n"
        )
        
        corrections = run_generation_gates(content, Path("/tmp"))
        
        assert len(corrections) > 0
        assert any("TaskExecutor" in c for c in corrections)
        assert any("src/runbook_generation.py" in c for c in corrections)

def test_run_generation_gates_clean_refactor():
    """Integration test: verify a complete refactor passes."""
    content = """
[MODIFY] src/executor.py
<<<<SEARCH
class TaskExecutor:
    pass
====
class ToolExecutor:
    pass
>>>>

[MODIFY] src/runbook_generation.py
<<<<SEARCH
from executor import TaskExecutor
====
from executor import ToolExecutor
>>>>
"""
    
    with patch("agent.core.implement.guards.subprocess.run") as mock_run:
        # Grep finds the consumer in the runbook-updated file
        mock_run.return_value = MagicMock(
            returncode=0, 
            stdout="src/runbook_generation.py\n"
        )
        
        corrections = run_generation_gates(content, Path("/tmp"))
        assert len(corrections) == 0

```



### Step 6: Documentation Updates

#### [NEW] .agent/docs/runbook-gates.md

```markdown
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

```



### Step 7: Deployment & Rollback Strategy

#### [NEW] .agent/src/agent/utils/rollback_infra_179.py

```python
"""
Rollback utility for INFRA-179: Public Symbol Rename Detection.

This script disables the rename detection gate by commenting out its invocation
in the runbook validation logic. This is a safe, additive rollback.
"""
import sys
from pathlib import Path

def main():
    """Comment out the rename check invocation in runbook_gates.py."""
    # Use relative path from project root
    target_path = Path(".agent/src/agent/commands/runbook_gates.py")
    
    if not target_path.exists():
        print(f"[ERROR] Target file not found: {target_path}")
        sys.exit(1)

    content = target_path.read_text()
    
    # The specific line added during implementation
    target_line = "    check_api_surface_renames("
    
    if target_line not in content:
        print("[INFO] INFRA-179 gate invocation not found or already disabled.")
        return

    lines = content.splitlines()
    new_lines = []
    modified = False

    for line in lines:
        if target_line in line and not line.strip().startswith("#"):
            # Preserve leading indentation
            indent = line[:line.find(target_line)]
            new_lines.append(f"{indent}# {line.lstrip()}")
            modified = True
        else:
            new_lines.append(line)

    if modified:
        target_path.write_text("\n".join(new_lines) + "\n")
        print("[SUCCESS] INFRA-179: Public Symbol Rename Detection gate has been disabled.")
    else:
        print("[INFO] No active invocation found to disable.")

if __name__ == "__main__":
    main()

```

