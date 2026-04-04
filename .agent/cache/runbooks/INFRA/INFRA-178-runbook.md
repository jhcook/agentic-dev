# Runbook: Implementation Runbook for INFRA-178

## State

PROPOSED

## Implementation Steps

### Step 1: Architecture & Design Review

#### [MODIFY] CHANGELOG.md

```

<<<SEARCH
## [Unreleased]
===
## [Unreleased] (Updated by story)

## [unreleased]

**Added**
- **Gate 3.7**: Static import resolution verification for new test files, checking against runbook symbols and environment packages (INFRA-178).
>>>

```

### Step 2: Implementation - Guard Logic & Observability

#### [MODIFY] .agent/src/agent/core/implement/guards.py

```

<<<SEARCH
    except SyntaxError as e:
        logger.warning(
            "projected_syntax_gate_fail",
            extra={"file": filepath.name, "error": str(e.msg), "line": e.lineno},
        )
        return format_projected_syntax_error(filepath, str(e.msg), e.lineno)
    except Exception as exc:
        return f"Warning: Could not project syntax for {filepath.name}: {exc}"
===
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
    """Verify that all imports in a [NEW] test file are resolvable.

    Validates imports against symbols defined within the current runbook session
    or resolvable via the environment (stdlib and installed packages).
    Ignores imports inside TYPE_CHECKING blocks to avoid false positives.

    Args:
        file_path: Repo-relative path of the file being checked.
        content: The Python source code of the block.
        session_symbols: Fully-qualified or basename symbols defined in the runbook.

    Returns:
        A correction prompt naming unresolved symbols, or None if validation passes.
    """
    import ast
    import importlib.util
    from pathlib import Path

    # 1. Exit early if naming pattern does not match tests (AC-5)
    _p = Path(file_path)
    is_test = (
        "tests/" in file_path.replace("\\", "/")
        or _p.name.startswith("test_")
        or _p.name.endswith("_test.py")
    )
    if not is_test:
        return None

    # 2. Parse content using ast.parse
    try:
        tree = ast.parse(content)
    except SyntaxError:
        # Syntax issues are handled by Gate 3.5; this gate becomes a no-op.
        return None

    unresolved = set()

    # 3. Walk the AST to find Import and ImportFrom nodes
    class ResolutionVisitor(ast.NodeVisitor):
        def visit_If(self, node: ast.If):
            # 4. Ignore nodes located within if TYPE_CHECKING: blocks (AC-4)
            tc_names = ("TYPE_CHECKING",)
            if isinstance(node.test, ast.Name) and node.test.id in tc_names:
                return
            if isinstance(node.test, ast.Attribute) and node.test.attr in tc_names:
                return
            self.generic_visit(node)

        def visit_Import(self, node: ast.Import):
            for alias in node.names:
                self._check_resolution(alias.name)

        def visit_ImportFrom(self, node: ast.ImportFrom):
            # Ignore relative imports as they require complex filesystem resolution
            if (node.level or 0) > 0:
                return
            if not node.module:
                return

            # AC-3: Resolvable via importlib.util.find_spec (Environment check)
            if importlib.util.find_spec(node.module) is not None:
                return

            # AC-1/AC-2: Resolve against symbols in the runbook session
            for alias in node.names:
                if alias.name not in session_symbols:
                    unresolved.add(f"from {node.module} import {alias.name}")

        def _check_resolution(self, module_name: str):
            # Check if module is in runbook or environment
            if module_name in session_symbols:
                return
            if importlib.util.find_spec(module_name) is None:
                unresolved.add(module_name)

    ResolutionVisitor().visit(tree)

    # 6. Log resolution failures using ADR-046 compliant telemetry
    if unresolved:
        unresolved_list = sorted(list(unresolved))
        logger.warning(
            "test_import_resolution_fail",
            extra={"file": file_path, "unresolved_symbols": unresolved_list},
        )
        return (
            f"UNRESOLVABLE IMPORTS in `{file_path}`:\n"
            + "\n".join(f"  - {s}" for s in unresolved_list)
            + "\n\nThe listed symbols/modules do not exist on disk and were not found "
            "in the current runbook session. If these are internal components, ensure "
            "they are implemented in a #### [NEW] block before importing them in tests."
        )

    return None
>>>

```



### Step 3: Implementation - Gate Orchestration

#### [MODIFY] .agent/src/agent/commands/runbook_gates.py

```

<<<SEARCH
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
===
import ast
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
>>>

```

<!-- DEDUP: .agent/src/agent/commands/runbook_gates.py already [MODIFY] in Step 1. All changes for this file should be consolidated there. -->

<!-- DEDUP: .agent/src/agent/commands/runbook_gates.py already [MODIFY] in Step 1. All changes for this file should be consolidated there. -->

<!-- DEDUP: .agent/src/agent/commands/runbook_gates.py already [MODIFY] in Step 1. All changes for this file should be consolidated there. -->

### Step 4: Security & Input Sanitization



### Step 5: Verification & Test Suite

#### [NEW] .agent/tests/unit/test_guards_import_resolution.py

```python
import pytest
from pathlib import Path
from agent.core.implement.guards import check_test_imports_resolvable

def test_check_test_imports_resolvable_cross_block():
    """AC-2: Verify that imports defined in other blocks in the same runbook pass."""
    content = "from agent.core.foo import MyClass\n"
    # Symbol 'MyClass' is simulated as being present in the runbook session index
    result = check_test_imports_resolvable(Path("tests/test_logic.py"), content, {"MyClass"})
    assert result is None

def test_check_test_imports_resolvable_stdlib():
    """AC-3: Verify that Python standard library imports pass validation."""
    content = "import os\nfrom pathlib import Path\nimport typing\n"
    result = check_test_imports_resolvable(Path("tests/test_logic.py"), content, set())
    assert result is None

def test_check_test_imports_resolvable_type_checking():
    """AC-4: Verify that imports inside if TYPE_CHECKING blocks are ignored."""
    content = """
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from agent.missing.module import GhostSymbol

def test_logic():
    pass
"""
    result = check_test_imports_resolvable(Path("tests/test_logic.py"), content, set())
    assert result is None

def test_check_test_imports_resolvable_ignores_non_test_files():
    """AC-5: Verify that the gate only applies to files matching test naming patterns."""
    content = "from agent.missing import Ghost\n"
    # Path does not contain 'tests/' and name does not start with 'test_'
    result = check_test_imports_resolvable(Path("agent/core/logic.py"), content, set())
    assert result is None

def test_check_test_imports_resolvable_unresolved_error():
    """AC-1: Verify that unresolvable imports in a test file return a correction prompt."""
    content = "from agent.core.logic import NonExistentSymbol\n"
    result = check_test_imports_resolvable(Path("tests/test_logic.py"), content, set())
    assert result is not None
    assert "IMPORT RESOLUTION FAILURE" in result
    assert "agent.core.logic.NonExistentSymbol" in result

```

#### [NEW] .agent/tests/commands/test_runbook_gates_import_resolution.py

```python
import pytest
from pathlib import Path
from agent.commands.runbook_gates import run_generation_gates
from agent.core.config import config

def test_run_generation_gates_detects_bad_test_import(tmp_path):
    """Integration test: verify that run_generation_gates returns a correction for unresolvable imports."""
    config.repo_root = tmp_path
    
    # Runbook content with a test file importing a non-existent symbol
    runbook_content = """
#### [NEW] tests/test_failure.py

```python
from agent.missing_module import MissingClass

def test_nothing():
    pass

```

"""
    # Call the orchestration loop gate
    _, correction_parts, _, _, _ = run_generation_gates(
        content=runbook_content,
        story_id="INFRA-178",
        story_content="Sample story",
        user_prompt="implement the fix",
        system_prompt="you are an agent",
        known_new_files=set(),
        attempt=1,
        max_attempts=3,
        gate_corrections=0,
        max_gate_corrections=5
    )
    
    # Check that the import resolution error is present in combined corrections
    assert any("IMPORT RESOLUTION FAILURE" in part for part in correction_parts)
    assert any("agent.missing_module.MissingClass" in part for part in correction_parts)

def test_run_generation_gates_passes_with_cross_block_dependency(tmp_path):
    """Integration test: verify that a test file importing a symbol defined in the SAME runbook passes."""
    config.repo_root = tmp_path
    
    # Runbook defines a class in one block and imports it in a test block
    runbook_content = """
#### [NEW] agent/core/logic.py

```python
class NewLogic:
    def execute(self):
        return True

```

#### [NEW] tests/test_logic.py

```python
from agent.core.logic import NewLogic

def test_new_logic():
    assert NewLogic().execute()

```

"""
    _, correction_parts, _, _, _ = run_generation_gates(
        content=runbook_content,
        story_id="INFRA-178",
        story_content="Sample story",
        user_prompt="implement logic and test",
        system_prompt="agent",
        known_new_files=set(),
        attempt=1,
        max_attempts=3,
        gate_corrections=0,
        max_gate_corrections=5
    )
    
    # Filter for Gate 3.7 specific errors
    import_failures = [p for p in correction_parts if "IMPORT RESOLUTION FAILURE" in p]
    assert not import_failures, f"Expected no import failures, got: {import_failures}"

```

### Step 6: Deployment & Rollback Strategy

#### [NEW] .agent/src/agent/utils/rollback_infra_178.py

```python
"""Rollback script for INFRA-178.

Reverts the additive Gate 3.7 changes in guards.py and runbook_gates.py.
"""
import re
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rollback_infra_178")

def rollback():
    """Removes Gate 3.7 logic and returns the pipeline to Gate 3.5 state."""
    root = Path(".")
    guards_path = root / ".agent/src/agent/core/implement/guards.py"
    gates_path = root / ".agent/src/agent/commands/runbook_gates.py"

    if guards_path.exists():
        content = guards_path.read_text(encoding="utf-8")
        # Remove the check_test_imports_resolvable function
        # This pattern matches from the function def until the next function def or end of file
        new_content = re.sub(
            r"\n\ndef check_test_imports_resolvable\(.*?\):\n(?:    .*\n?)*",
            "\n",
            content,
            flags=re.DOTALL
        )
        if new_content != content:
            guards_path.write_text(new_content, encoding="utf-8")
            logger.info("Successfully removed check_test_imports_resolvable from guards.py")

    if gates_path.exists():
        content = gates_path.read_text(encoding="utf-8")
        
        # 1. Remove from import list
        content = content.replace("check_test_imports_resolvable,\n    ", "")
        content = content.replace(", check_test_imports_resolvable", "")
        
        # 2. Remove _build_runbook_symbol_index helper
        content = re.sub(
            r"\n\ndef _build_runbook_symbol_index\(.*?\):\n(?:    .*\n?)*",
            "\n",
            content,
            flags=re.DOTALL
        )
        
        # 3. Remove Gate 3.7 orchestration block
        # Anchor: after gate35.corrections attribute
        content = re.sub(
            r"\s+# Gate 3\.7: Test Import Resolution.*?import_span\.set_attribute\(\"gate37\.corrections\", len\(correction_parts\)\)",
            "",
            content,
            flags=re.DOTALL
        )
        
        gates_path.write_text(content, encoding="utf-8")
        logger.info("Successfully reverted orchestration changes in runbook_gates.py")

if __name__ == "__main__":
    try:
        rollback()
        logger.info("Rollback of INFRA-178 complete.")
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
"

```



