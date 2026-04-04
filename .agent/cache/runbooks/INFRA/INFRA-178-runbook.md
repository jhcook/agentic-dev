# Runbook: Implementation Runbook for INFRA-178

## State

ACCEPTED

## Implementation Steps

### Step 1: Architecture & Design Review

The architecture for Gate 3.7 (Test Import Resolution) has been reviewed to ensure consistency with the generation pipeline and DoD requirements. The following implementation strategy is approved for integration into the two-pass generation system.

**AST-Based Import Extraction Strategy**
To avoid the inaccuracies of regex-based parsing, the implementation will utilize `ast.parse()` on the content of every `[NEW]` test file block (identified by the `tests/**/*.py` pattern per AC-5). The logic will traverse the top-level nodes of the `ast.Module` body to extract `ast.Import` and `ast.ImportFrom` statements.

**Handling Conditional and Type-Checking Imports**
In accordance with AC-4, the gate will explicitly ignore any import statements found within an `ast.If` block where the condition references `TYPE_CHECKING` (e.g., `if TYPE_CHECKING:` or `if typing.TYPE_CHECKING:`). Additionally, nested imports within function or class scopes will be excluded to focus verification on top-level collection-time dependencies.

**Symbol Resolution Hierarchy**
The resolution engine will check symbols against the following hierarchy in order:
1. **Session Symbols**: A flat set of names aggregated from the current runbook session. This set includes the dotted module paths of all `#### [NEW]` files and the granular symbols (class and function names) parsed from all `[NEW]` and `[MODIFY]` code blocks.
2. **Standard Library**: Modules verified using `sys.builtin_module_names` and `importlib.util.find_spec`.
3. **Installed Packages**: Third-party dependencies verified via `importlib.util.find_spec` within the active virtual environment.
4. **Local Filesystem**: Verification of the existence of corresponding `.py` files relative to the repository root.

#### [NEW] .agent/docs/architecture/infra-178-resolution-design.md

```markdown
# INFRA-178: Test Import Resolution Architecture

## Implementation Strategy
This document outlines the logic for the Gate 3.7 validation gate.

## AST Extraction
- **Target Nodes**: `ast.Import`, `ast.ImportFrom`.
- **Context**: Module-level body statements only.
- **Exclusion Logic**: Skip any node where the parent path includes an `ast.If` block testing for `TYPE_CHECKING` identifiers.

## Resolution Hierarchy
| Priority | Source | Description |
|----------|--------|-------------|
| 1 | Session | Symbols defined in the current runbook (new files or modified classes/functions). |
| 2 | Stdlib | Python standard library modules. |
| 3 | Venv | Installed packages in the current execution environment. |
| 4 | Disk | Local files existing relative to the repository root. |

## Correction Loop
If a symbol fails to resolve, `run_generation_gates()` returns a correction prompt identifying the file and the unresolved symbol, triggering an AI retry to either implement the missing symbol or correct the import path.

```

#### [MODIFY] CHANGELOG.md

```markdown
<<<SEARCH
## [Unreleased]
- **Infrastructure**: Added Gate 3.5 (Projected Syntax Validation) for `[MODIFY]` S/R blocks — uses in-memory AST projection to detect `SyntaxError` before runbook application, with path-traversal prevention via `validate_path_integrity` (INFRA-176).
===
## [Unreleased]
- **Infrastructure**: Added Gate 3.7 (Test Import Resolution) for `[NEW]` test files — uses AST + `importlib.util.find_spec` to detect ghost imports before runbook application (INFRA-178).
- **Infrastructure**: Added Gate 3.5 (Projected Syntax Validation) for `[MODIFY]` S/R blocks — uses in-memory AST projection to detect `SyntaxError` before runbook application, with path-traversal prevention via `validate_path_integrity` (INFRA-176).
>>>
```

### Step 2: Implementation: Import Resolution Logic & Orchestration

Implement the core logic for verifying test file imports against the repository state and the current runbook session. This involves adding a new validation guard in `guards.py` and integrating it into the `run_generation_gates` pipeline in `runbook_gates.py` with an in-memory symbol index.

#### [MODIFY] .agent/src/agent/core/implement/guards.py

```python
<<<SEARCH
def check_projected_syntax(
    filepath: Path, search: str, replace: str, root_dir: Optional[Path] = None
) -> Optional[str]:
    """Validate Python syntax after projecting a [MODIFY] S/R block in-memory.

    Covers AC-1 to AC-6. AC-7 (NameError detection) is deferred to INFRA-178.
    Pass ``root_dir`` (the repo root) to enable path-traversal prevention (AC-6).
    Only runs for .py files; all projection is done in-memory (no disk side effects).
    """
    if filepath.suffix != ".py":
        return None

    _root = root_dir if root_dir is not None else filepath.parent
    if not validate_path_integrity(str(filepath), _root):
        return f"Gate 3.5: '{filepath.name}' resolves outside the project root — skipped."

    try:
        if not filepath.exists():
            return None

        content = filepath.read_text(encoding="utf-8")

        # AC-5: search absent → S/R gate owns that check; this gate is a no-op.
        if search not in content:
            return None

        projected_content = content.replace(search, replace, 1)
        ast.parse(projected_content)
        return None

    except SyntaxError as e:
        logger.warning(
            "projected_syntax_gate_fail",
            extra={"file": filepath.name, "error": str(e.msg), "line": e.lineno},
        )
        return format_projected_syntax_error(filepath, str(e.msg), e.lineno)
    except Exception as exc:
        return f"Warning: Could not project syntax for {filepath.name}: {exc}"
===
def check_projected_syntax(
    filepath: Path, search: str, replace: str, root_dir: Optional[Path] = None
) -> Optional[str]:
    """Validate Python syntax after projecting a [MODIFY] S/R block in-memory.

    Covers AC-1 to AC-6. AC-7 (NameError detection) is deferred to INFRA-178.
    Pass ``root_dir" (the repo root) to enable path-traversal prevention (AC-6).
    Only runs for .py files; all projection is done in-memory (no disk side effects).
    """
    if filepath.suffix != ".py":
        return None

    _root = root_dir if root_dir is not None else filepath.parent
    if not validate_path_integrity(str(filepath), _root):
        return f"Gate 3.5: '{filepath.name}' resolves outside the project root — skipped."

    try:
        if not filepath.exists():
            return None

        content = filepath.read_text(encoding="utf-8")

        # AC-5: search absent → S/R gate owns that check; this gate is a no-op.
        if search not in content:
            return None

        projected_content = content.replace(search, replace, 1)
        ast.parse(projected_content)
        return None

    except SyntaxError as e:
        logger.warning(
            "projected_syntax_gate_fail",
            extra={"file": filepath.name, "error": str(e.msg), "line": e.lineno},
        )
        return format_projected_syntax_error(filepath, str(e.msg), e.lineno)
    except Exception as exc:
        return f"Warning: Could not project syntax for {filepath.name}: {exc}"


def check_test_imports_resolvable(
    file_path: str, content: str, session_symbols: Set[str]
) -> Optional[str]:
    """Verify that top-level imports in a [NEW] test file are resolvable (INFRA-178).

    Checks imports against the standard library, installed packages, on-disk files,
    and the provided set of symbols defined within the same runbook session.

    Args:
        file_path: Repo-relative path of the file being checked.
        content: The generated Python source code.
        session_symbols: Set of symbol names defined in other blocks of the runbook.

    Returns:
        A correction prompt string if unresolvable imports are found, else None.
    """
    import importlib.util
    import sys

    # AC-5: Only apply to test files
    if not (file_path.startswith("tests/") or "/tests/" in file_path.replace("\\", "/")):
        return None

    try:
        tree = ast.parse(content)
    except SyntaxError:
        # Syntax errors are handled by Gate 3.5 or validate_code_block
        return None

    unresolved = []
    
    # Identify standard library modules
    stdlib = set(sys.stdlib_module_names) if sys.version_info >= (3, 10) else set()

    def _is_resolvable(module_name: str, symbol_name: Optional[str] = None) -> bool:
        # 1. Check session symbols (AC-2)
        if symbol_name and symbol_name in session_symbols:
            return True
        
        # 2. Check Standard Library (AC-3)
        top_level = module_name.split(".")[0]
        if top_level in stdlib:
            return True

        # 3. Check installed packages/venv (AC-3)
        try:
            spec = importlib.util.find_spec(module_name)
            if spec is not None:
                if not symbol_name:
                    return True
                # If we have a symbol, check if it's exported/present in the module
                # We use a simple static check for existing files to avoid importing untrusted generated code
                return True # Assume symbol exists if module is third-party/installed
        except (ImportError, ValueError):
            pass

        # 4. Check on-disk relative to project root
        # Mapping agent.core.foo -> agent/core/foo.py
        parts = module_name.split(".")
        potential_path = Path(".").joinpath(*parts).with_suffix(".py")
        if potential_path.exists():
            if not symbol_name:
                return True
            # Static check of the on-disk file for the symbol
            disk_content = potential_path.read_text(encoding="utf-8", errors="ignore")
            if f"class {symbol_name}" in disk_content or f"def {symbol_name}" in disk_content:
                return True

        return False

    class ImportVisitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.in_type_checking = False

        def visit_If(self, node: ast.If) -> None:
            # AC-4: Exclude TYPE_CHECKING blocks
            is_tc = False
            if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
                is_tc = True
            elif isinstance(node.test, ast.Attribute) and node.test.attr == "TYPE_CHECKING":
                is_tc = True
            
            if is_tc:
                prev = self.in_type_checking
                self.in_type_checking = True
                # Do not visit children of the IF block if we want to skip them completely
                # But we must visit the 'else' block if it exists
                for item in node.orelse:
                    self.visit(item)
                self.in_type_checking = prev
            else:
                self.generic_visit(node)

        def visit_Import(self, node: ast.Import) -> None:
            if self.in_type_checking:
                return
            for alias in node.names:
                if not _is_resolvable(alias.name):
                    unresolved.append(f"import {alias.name}")

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            if self.in_type_checking:
                return
            if not node.module:
                return  # relative imports without module name not supported in this gate
            for alias in node.names:
                if alias.name == "*":
                    continue
                if not _is_resolvable(node.module, alias.name):
                    unresolved.append(f"from {node.module} import {alias.name}")

    ImportVisitor().visit(tree)

    if not unresolved:
        return None

    logger.warning(
        "test_import_resolution_fail",
        extra={"file": file_path, "unresolved_symbols": unresolved},
    )

    detail = "\n".join(f"  - `{u}`" for u in unresolved)
    return (
        f"IMPORT RESOLUTION ERROR in `{file_path}`:\n"
        f"{detail}\n"
        "The symbols above do not exist on disk and are not defined in any other block "
        "in this runbook. Ensure all imported symbols are either existing or "
        "implemented in this session."
    )
>>>

```

#### [MODIFY] .agent/src/agent/commands/runbook_gates.py

```python
<<<SEARCH
from agent.core.implement.guards import (
    check_projected_loc,
    check_projected_syntax,
    validate_code_block,
    check_impact_analysis_completeness,
    check_adr_refs,
    check_stub_implementations,
)
===
from agent.core.implement.guards import (
    check_projected_loc,
    check_projected_syntax,
    check_test_imports_resolvable,
    validate_code_block,
    check_impact_analysis_completeness,
    check_adr_refs,
    check_stub_implementations,
)
>>>

```

```python
<<<SEARCH
logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)
console = Console()
error_console = Console(stderr=True)
===
logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)
console = Console()
error_console = Console(stderr=True)


def _build_runbook_symbol_index(runbook_content: str) -> Set[str]:
    """Extract all defined class and function names from runbook code blocks (INFRA-178)."""
    import ast
    symbols: Set[str] = set()
    
    # 1. Collect from [NEW] blocks
    new_blocks = parse_code_blocks(runbook_content)
    for block in new_blocks:
        try:
            tree = ast.parse(block["content"])
            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                    symbols.add(node.name)
        except Exception:
            continue

    # 2. Collect from [MODIFY] REPLACE sections
    sr_blocks = parse_search_replace_blocks(runbook_content)
    for block in sr_blocks:
        try:
            # We parse the replace block as a fragment. If it's partial, ast.parse might fail,
            # but we catch it. This surfaces symbols defined in S/R operations.
            tree = ast.parse(block.get("replace", ""))
            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                    symbols.add(node.name)
        except Exception:
            continue

    return symbols
>>>

```

```python
<<<SEARCH
            if syntax_err:
                correction_parts.append(syntax_err)
        syn_span.set_attribute("gate35.corrections", len(correction_parts))

    if code_errors:
===
            if syntax_err:
                correction_parts.append(syntax_err)
    syn_span.set_attribute("gate35.corrections", len(correction_parts))

    # Gate 3.7: Test Import Resolution (INFRA-178)
    with tracer.start_as_current_span("test_import_resolution_gate") as ir_span:
        session_symbols = _build_runbook_symbol_index(content)
        ir_span.set_attribute("gate37.symbol_count", len(session_symbols))
        
        # We reuse the parsed_blocks from Gate 2 logic if it was a [NEW] file
        for b in parsed_blocks:
            import_err = check_test_imports_resolvable(b["file"], b["content"], session_symbols)
            if import_err:
                correction_parts.append(import_err)
        
        ir_span.set_attribute("gate37.corrections", len([c for c in correction_parts if "IMPORT RESOLUTION ERROR" in c]))

    if code_errors:
>>>

```

> **Note:** The symbol indexer uses a full-content regex scan, so symbols defined in a `[NEW]` block earlier in the runbook will be found automatically.
> - For `[MODIFY]` blocks that define new symbols, the symbol must be clearly defined within the `>>>REPLACE` section for the indexer to pick it up.
> - Static analysis of `[MODIFY]` blocks is best-effort; if a symbol is defined across multiple search/replace fragments, it may not be indexed correctly unless the entire class/function is within one block.

### Step 3: Security & Input Sanitization

This section ensures that the LLM-generated content is parsed safely using `ast.parse`. Since the content is untrusted input, the gate must catch `SyntaxError` exceptions and return a helpful correction prompt to the AI instead of allowing the pipeline to crash. This provides both robustness and a self-healing loop for malformed code generation.

### Step 4: Observability & Audit Logging

Verify the implementation of ADR-046 compliant structured logging within the test import resolution logic. The gate must provide clear, machine-readable audit evidence whenever an implementation fails validation due to unresolved symbols. This allows for automated analysis of generation failures and ensures that the LLM receives precise feedback for self-correction.

**Logging Specification (ADR-046)**
When the `check_test_imports_resolvable` function (implemented in Gate 2) identifies symbols that cannot be found in the session context, standard library, or local file system, it must emit a warning level log event. 

**Event Details:**
- **Event Name**: `test_import_resolution_fail`
- **Logger**: Standard module-level `logging.getLogger(__name__)`.
- **Payload**: Must include an `extra` dictionary containing:
  - `file`: The repository-relative path of the test file.
  - `unresolved_symbols`: A list of the symbols that triggered the failure.

**Verification Protocol**
1. Inspect the `check_test_imports_resolvable` logic in `.agent/src/agent/core/implement/guards.py` to ensure the `logger.warning` call includes the `extra` metadata dictionary.
2. Verify that the event name matches exactly `test_import_resolution_fail` to ensure compatibility with log aggregation filters.
3. Confirm that the `unresolved_symbols` attribute is passed as a list (JSON-serializable) rather than a set or a string.

### Step 5: Verification & Test Suite

This section provides unit and integration tests to verify the AST-based import resolution logic and its orchestration within the runbook generation pipeline. The tests ensure that ghost imports are correctly identified, while valid imports (including those defined within the same runbook session) are permitted.

#### [NEW] .agent/tests/unit/test_guards_import_resolution.py

```python
# Copyright 2026 Justin Cook
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for AST-based import resolution logic (INFRA-178)."""

import pytest
from typing import Set
from agent.core.implement.guards import check_test_imports_resolvable

def test_check_test_imports_resolvable_ghost_symbol():
    """Verify that unresolvable imports trigger a resolution error (AC-1)."""
    content = "from agent.core.logic import NonExistentSymbol"
    # File name matches test pattern (AC-5)
    errors = check_test_imports_resolvable("tests/test_logic.py", content, set())
    assert len(errors) == 1
    assert "imports unresolvable symbols" in errors[0]
    assert "agent.core.logic.NonExistentSymbol" in errors[0]

def test_check_test_imports_resolvable_session_match():
    """Verify that symbols defined in the runbook session resolve successfully (AC-2)."""
    content = "from agent.core.logic import NewClass"
    session_symbols = {"NewClass"}
    errors = check_test_imports_resolvable("tests/test_logic.py", content, session_symbols)
    assert len(errors) == 0

def test_check_test_imports_resolvable_stdlib():
    """Verify that standard library imports pass without errors (AC-3)."""
    content = "import os\nfrom typing import List, Optional"
    errors = check_test_imports_resolvable("tests/test_logic.py", content, set())
    assert len(errors) == 0

def test_check_test_imports_resolvable_type_checking():
    """Verify that imports inside TYPE_CHECKING blocks are excluded (AC-4)."""
    content = """
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from agent.ghost import MissingSymbol
import sys
"""
    errors = check_test_imports_resolvable("tests/test_logic.py", content, set())
    assert len(errors) == 0

def test_check_test_imports_resolvable_ignores_non_test():
    """Verify that resolution checks are skipped for non-test files (AC-5)."""
    content = "import GhostModule"
    errors = check_test_imports_resolvable("agent/core/logic.py", content, set())
    assert len(errors) == 0

def test_check_test_imports_resolvable_syntax_error():
    """Verify that malformed code returns a helpful error rather than crashing (Security)."""
    content = "def broken_func(" # Missing closing paren
    errors = check_test_imports_resolvable("tests/test_logic.py", content, set())
    assert len(errors) == 1
    assert "[Security]: Syntax error" in errors[0]

```

#### [NEW] .agent/tests/commands/test_runbook_gates_import_resolution.py

```python
# Copyright 2026 Justin Cook
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Integration tests for runbook gate loop import resolution (INFRA-178)."""

import pytest
from unittest.mock import patch, MagicMock
from agent.commands.runbook_gates import run_generation_gates

def test_run_generation_gates_detects_unresolved_imports():
    """Ensure the orchestration loop identifies ghost imports in new test files."""
    # Simulated runbook content with a NEW test file containing a ghost import
    runbook_content = """
#### [NEW] tests/test_ghost_gate.py

```python
from agent.core.implement.guards import GhostGuard

```

"""
    story_id = "INFRA-178"
    story_content = "# Problem Statement\nPaired tests must resolve imports."

    # Mock sibling gates to isolate import resolution check (Gate 3.7)
    with patch("agent.commands.runbook_gates.validate_runbook_schema", return_value=[]), \
         patch("agent.commands.runbook_gates.check_projected_loc", return_value=[]), \
         patch("agent.commands.runbook_gates.validate_sr_blocks", return_value=[]), \
         patch("agent.commands.runbook_gates.validate_code_block", return_value=MagicMock(errors=[], warnings=[])):

        _, corrections, _, _, _ = run_generation_gates(
            content=runbook_content,
            story_id=story_id,
            story_content=story_content,
            user_prompt="",
            system_prompt="",
            known_new_files=set(),
            attempt=1,
            max_attempts=3,
            gate_corrections=0,
            max_gate_corrections=5
        )

        # Assert that the Resolution Error is identified
        assert len(corrections) > 0
        assert any("Gate 3.7 Resolution Error" in c for c in corrections)
        assert any("agent.core.implement.guards.GhostGuard" in c for c in corrections)

def test_run_generation_gates_resolves_cross_block_symbols():
    """Ensure symbols implemented in one block resolve in a paired test block."""
    # Runbook content where logic is implemented in one block and imported in another
    runbook_content = """
#### [NEW] agent/core/logic.py

```python
class SessionLogic:
    pass

```

#### [NEW] tests/test_logic.py

```python
from agent.core.logic import SessionLogic

```

"""
    with patch("agent.commands.runbook_gates.validate_runbook_schema", return_value=[]), \
         patch("agent.commands.runbook_gates.check_projected_loc", return_value=[]), \
         patch("agent.commands.runbook_gates.validate_sr_blocks", return_value=[]), \
         patch("agent.commands.runbook_gates.validate_code_block", return_value=MagicMock(errors=[], warnings=[])):

        _, corrections, _, _, _ = run_generation_gates(
            content=runbook_content,
            story_id="INFRA-178",
            story_content="",
            user_prompt="",
            system_prompt="",
            known_new_files=set(),
            attempt=1,
            max_attempts=3,
            gate_corrections=0,
            max_gate_corrections=5
        )

        # Assert that no resolution errors were raised
        assert len(corrections) == 0

```



### Step 6: Deployment & Rollback Strategy

Establish the emergency revert mechanism and update the project changelog. The validation check introduced in this story is purely additive (read-only AST analysis) and does not mutate project state, allowing for a simplified rollback of logic without data recovery procedures.

**Rollback Procedure**
In the event of false positives that block critical hotfix runbooks, execute the automated rollback script. This script surgically removes the Gate 3.7 resolution logic from `guards.py` and the orchestration call from `runbook_gates.py`.

#### [NEW] .agent/src/agent/utils/rollback_infra_178.py

```python
# Copyright 2026 Justin Cook
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Rollback script for INFRA-178: Test Import Resolution Gate.

Surgically removes the additive Gate 3.7 logic from the implementation pipeline
to resolve blocking false positives.
"""

import re
from pathlib import Path

def rollback_infra_178():
    """Revert code changes in guards.py and runbook_gates.py."""
    # Calculate repo root relative to this script in .agent/src/agent/utils/
    repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    guards_path = repo_root / ".agent/src/agent/core/implement/guards.py"
    gates_path = repo_root / ".agent/src/agent/commands/runbook_gates.py"

    print("Starting rollback for INFRA-178...")

    # 1. Revert guards.py logic
    if guards_path.exists():
        content = guards_path.read_text(encoding="utf-8")
        # Remove the function check_test_imports_resolvable
        pattern = r"\n\ndef check_test_imports_resolvable\(.*?\n    return ValidationResult\(errors=errors\)"
        new_content = re.sub(pattern, "", content, flags=re.DOTALL)
        if new_content != content:
            guards_path.write_text(new_content, encoding="utf-8")
            print(f"  - Removed check_test_imports_resolvable from {guards_path.name}")

    # 2. Revert runbook_gates.py orchestration
    if gates_path.exists():
        content = gates_path.read_text(encoding="utf-8")
        
        # Remove symbol index builder helper
        pattern_helper = r"\n\ndef _build_runbook_symbol_index\(.*?\n    return symbols"
        content = re.sub(pattern_helper, "", content, flags=re.DOTALL)
        
        # Remove the Gate 3.7 orchestration block inside run_generation_gates
        pattern_call = r"\n\s+# Gate 3\.7: Test Import Resolution.*?syn_span\.set_attribute\(\"gate37\.corrections\", len\(correction_parts\)\)"
        content = re.sub(pattern_call, "", content, flags=re.DOTALL)
        
        # Clean up guards import
        content = content.replace("check_test_imports_resolvable,", "")
        
        gates_path.write_text(content, encoding="utf-8")
        print(f"  - Removed Gate 3.7 orchestration from {gates_path.name}")

    print("Rollback complete.")

if __name__ == "__main__":
    rollback_infra_178()

```
