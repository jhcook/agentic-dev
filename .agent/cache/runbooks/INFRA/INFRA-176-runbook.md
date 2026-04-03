# Runbook: Implementation Runbook for INFRA-176

## State

ACCEPTED

## Implementation Steps

### Step 1: Architecture & Design Review

The architecture for Gate 3.5 has been audited to ensure it provides a robust "shift-left" for syntax validation during the runbook generation loop. This section verifies that the proposed logic for projected syntax checking is aligned with existing implementation engines.

**Projection Logic Parity**
The core of this check relies on simulating the file state after a `[MODIFY]` block is applied. To ensure zero false positives, the logic must utilize `str.replace(search_text, replace_text, 1)` exactly as found in the `assembly_engine`. This ensures that only the first occurrence is replaced, matching the agent's verbatim application strategy. The operation will be performed on a UTF-8 encoded string buffer, satisfying the requirement for in-memory safety without disk side effects.

**Validation Framework**
Utilizing the standard library `ast.parse()` is appropriate for the current Python 3.10+ runtime. The parser returns a `SyntaxError` or `IndentationError` with detailed metadata (line numbers and offsets). The design specifies that this metadata must be captured and transformed into a correction prompt, allowing the AI to identify the exact line in its `REPLACE` block that caused the violation.

**Gate Sequence Verification**
The validation check must be integrated into `run_generation_gates` within `.agent/src/agent/commands/runbook_gates.py`. It is positioned strategically after the search-match gate; this ensures that syntax errors are only reported if the transformation is valid from a SEARCH/REPLACE perspective, preventing the AI from receiving conflicting feedback about missing search text and broken syntax simultaneously.

**Troubleshooting & Performance**
- **AC-3 Compliance**: The logic will explicitly check for the `.py` suffix to avoid overhead on markdown or configuration files.
- **AC-5 Handling**: If the projection buffer is identical to the source buffer (no match), the AST parse is skipped to optimize performance.

#### [MODIFY] CHANGELOG.md

```markdown
<<<SEARCH
## [Unreleased]
===
## [Unreleased]
- **Infrastructure**: Added Gate 3.5 (Projected Syntax Validation) for `[MODIFY]` S/R blocks — uses in-memory AST projection to detect `SyntaxError` before runbook application, with path-traversal prevention via `validate_path_integrity` (INFRA-176).
>>>

```

### Step 2: Core Logic Implementation

This section implements the `check_projected_syntax` guard to prevent the generation of runbooks that would corrupt Python source files during implementation. The logic performs an in-memory string replacement mirroring the implementation engine's behavior and validates the result using Python's Abstract Syntax Tree (AST) parser.

#### [MODIFY] .agent/src/agent/core/implement/guards.py

```python
<<<SEARCH
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
===
import ast
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from agent.utils.path_utils import validate_path_integrity
>>>
<<<SEARCH
def apply_change_to_file(
===
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


def apply_change_to_file(
>>>

```

#### [MODIFY] .agent/src/agent/commands/runbook_gates.py

```python
<<<SEARCH
from typing import List, Optional, Set, Tuple
===
from typing import Dict, List, Optional, Set, Tuple
>>>
<<<SEARCH
from agent.core.implement.guards import (
    check_projected_loc,
    validate_code_block,
    check_impact_analysis_completeness,
    check_adr_refs,
    check_stub_implementations,
)
===
from agent.core.implement.guards import (
    check_projected_loc,
    check_projected_syntax,
    validate_code_block,
    check_impact_analysis_completeness,
    check_adr_refs,
    check_stub_implementations,
)
>>>
<<<SEARCH
    with tracer.start_as_current_span("validate_code_gates") as span:
        parsed_blocks = parse_code_blocks(content)
        for b in parsed_blocks:
            res = validate_code_block(b["file"], b["content"])
            code_errors.extend(res.errors)
            code_warnings.extend(res.warnings)
===
    with tracer.start_as_current_span("validate_code_gates") as span:
        parsed_blocks = parse_code_blocks(content)
        for b in parsed_blocks:
            res = validate_code_block(b["file"], b["content"])
            code_errors.extend(res.errors)
            code_warnings.extend(res.warnings)

    # Gate 3.5: Projected Syntax Validation for [MODIFY] S/R blocks (AC-1 to AC-6)
    with tracer.start_as_current_span("validate_projected_syntax_gate") as syn_span:
        sr_blocks: List[Dict[str, str]] = parse_search_replace_blocks(content)
        syn_span.set_attribute("gate35.block_count", len(sr_blocks))
        for block in sr_blocks:
            syntax_err: Optional[str] = check_projected_syntax(
                config.repo_root / block["file"],
                block.get("search", ""),
                block.get("replace", ""),
                root_dir=config.repo_root,
            )
            if syntax_err:
                correction_parts.append(syntax_err)
        syn_span.set_attribute("gate35.corrections", len(correction_parts))
>>>

```

### Step 3: Security & Input Sanitization

This section establishes the security boundary for the projected syntax gate. `validate_path_integrity` is placed in a dedicated `agent.utils.path_utils` module so that both `agent.core` and `agent.commands` layers can import it without creating a downward architectural dependency. `agent.commands.gates` re-exports it for backward compatibility.

**AST-Only Verification Strategy**
The validation logic is explicitly restricted to `ast.parse()`. Unlike `eval()`, `exec()`, or dynamic imports, `ast.parse()` only generates a data representation of the source code, allowing the gate to detect `SyntaxError` exceptions without executing any code.

#### [NEW] .agent/src/agent/utils/path_utils.py

```python
"""Shared path-integrity utilities.

Placed in agent.utils so both agent.core and agent.commands can import without
creating a downward architectural dependency.
"""
from pathlib import Path


def validate_path_integrity(target_path: str, root_dir: Path) -> bool:
    """Verify that target_path resolves within root_dir (prevents path traversal)."""
    try:
        resolved_root = root_dir.resolve()
        resolved_target = (root_dir / target_path).resolve()
        return str(resolved_target).startswith(str(resolved_root))
    except (ValueError, RuntimeError):
        return False
```

#### [MODIFY] .agent/src/agent/commands/gates.py

```python
<<<SEARCH
from agent.core.logger import get_logger

class GateStatus(Enum):
===
from agent.core.logger import get_logger
from agent.utils.path_utils import validate_path_integrity  # noqa: F401 — re-exported

class GateStatus(Enum):
>>>

```

### Step 4: Observability & Audit Logging

Syntax validation failures are surfaced via a direct `logger.warning("projected_syntax_gate_fail", ...)` call inside `guards.py` (no separate telemetry helper needed). The correction prompt is formatted by `format_projected_syntax_error` in `validation_formatter.py`, which sanitises paths and produces AI-readable feedback.

The Gate 3.5 integration point in `run_generation_gates` is wrapped in an OpenTelemetry span (`validate_projected_syntax_gate`) that records block count and correction count as span attributes, satisfying ADR-046 structured observability.

#### [MODIFY] .agent/src/agent/utils/validation_formatter.py

```python
<<<SEARCH
from typing import Any, Dict, List
===
from pathlib import Path
from typing import Any, Dict, List, Optional
>>>
<<<SEARCH
def format_implementation_summary(
    applied_files: List[str],
    warned_files: Dict[str, List[str]],
    rejected_files: List[str]
) -> Panel:
===
def format_projected_syntax_error(
    file_path: Path,
    error_msg: str,
    line: Optional[int],
) -> str:
    """
    Format a projected SyntaxError for the AI correction prompt.

    Sanitizes paths to protect sensitive metadata and provides explicit tips.
    """
    rel_file = file_path.name
    line_info = f" at line {line}" if line is not None else ""
    return (
        f"Gate 3.5 Failure: Your [MODIFY] block for {rel_file} produces invalid Python "
        f"syntax{line_info}. Error: {error_msg}. "
        "Re-emit the complete, syntactically valid REPLACE block with correct indentation "
        "and balanced brackets."
    )


def format_implementation_summary(
    applied_files: List[str],
    warned_files: Dict[str, List[str]],
    rejected_files: List[str]
) -> Panel:
>>>

```

### Step 5: Verification & Test Suite

Implement a rigorous verification suite for Gate 3.5. This includes unit tests for the projection and parsing logic in `guards.py` and integration tests to ensure that the runbook generation loop correctly intercepts and reports syntax errors back to the AI via correction prompts.

#### [NEW] .agent/tests/unit/test_guards_syntax.py

```python
"""Unit tests for check_projected_syntax (Gate 3.5).

All unit-level isolation tests for check_projected_syntax live here.
Integration tests (run_generation_gates pipeline) live in
tests/commands/test_runbook_gates_syntax.py.
"""
import tempfile
from pathlib import Path
from unittest.mock import patch
from agent.core.implement.guards import check_projected_syntax

_BYPASS_PATH_CHECK = patch(
    "agent.utils.path_utils.validate_path_integrity", return_value=True
)


@_BYPASS_PATH_CHECK
def test_check_projected_syntax_valid_python(mock_vi, tmp_path):
    """AC-2: Valid Python replacement should pass (return None)."""
    file_path = tmp_path / "valid.py"
    file_path.write_text("def hello():\n    print('hi')", encoding="utf-8")
    result = check_projected_syntax(file_path, "print('hi')", "print('hello world')", root_dir=tmp_path)
    assert result is None


@_BYPASS_PATH_CHECK
def test_check_projected_syntax_invalid_indentation(mock_vi, tmp_path):
    """AC-1: REPLACE that produces an IndentationError should be caught."""
    file_path = tmp_path / "indent_error.py"
    file_path.write_text("def hello():\n    pass", encoding="utf-8")
    result = check_projected_syntax(file_path, "    pass", "print('no indent')", root_dir=tmp_path)
    assert result is not None
    assert "Gate 3.5" in result


def test_check_projected_syntax_skip_non_python(tmp_path):
    """AC-3: Non-Python files are skipped (before path check)."""
    file_path = tmp_path / "config.yaml"
    file_path.write_text("key: value", encoding="utf-8")
    assert check_projected_syntax(file_path, "key: value", "invalid:::syntax") is None


@_BYPASS_PATH_CHECK
def test_check_projected_syntax_search_missing(mock_vi, tmp_path):
    """AC-5: Missing search text → no-op."""
    file_path = tmp_path / "missing.py"
    file_path.write_text("x = 1", encoding="utf-8")
    assert check_projected_syntax(file_path, "y = 2", "z = 3", root_dir=tmp_path) is None


@_BYPASS_PATH_CHECK
@patch("agent.core.implement.guards.logger")
def test_check_projected_syntax_emits_telemetry(mock_logger, mock_vi, tmp_path):
    """SyntaxError triggers a structured warning log event."""
    file_path = tmp_path / "fail.py"
    file_path.write_text("x = 1", encoding="utf-8")
    result = check_projected_syntax(file_path, "x = 1", "x = (", root_dir=tmp_path)
    assert result is not None
    mock_logger.warning.assert_called_once()
    assert mock_logger.warning.call_args.args[0] == "projected_syntax_gate_fail"


def test_check_projected_syntax_path_traversal_blocked(tmp_path):
    """AC-6: Paths outside root_dir are blocked by real validate_path_integrity."""
    external_path = tmp_path / "secret.py"
    external_path.write_text("password = 'hunter2'", encoding="utf-8")
    with tempfile.TemporaryDirectory() as other_root:
        result = check_projected_syntax(
            external_path, "password = 'hunter2'", "x = 1", root_dir=Path(other_root)
        )
    assert result is not None
    assert "outside the project root" in result
```

#### [NEW] .agent/tests/commands/test_runbook_gates_syntax.py

```python
"""Integration tests: Gate 3.5 projected syntax validation pipeline.

Unit-level isolation tests for check_projected_syntax live in
tests/unit/test_guards_syntax.py.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch


def _make_modify_runbook(file_path: str, search: str, replace: str) -> str:
    return (
        "## State\n\nACCEPTED\n\n"
        "## Implementation Steps\n\n### Step 1\n\n"
        f"#### [MODIFY] {file_path}\n\n"
        "```python\n"
        f"<<<SEARCH\n{search}===\n{replace}>>>\n"
        "```\n"
    )


def test_gate35_syntax_violation_appears_in_correction_parts(tmp_path: Path) -> None:
    """Syntactically invalid REPLACE → Gate 3.5 message in correction_parts."""
    from agent.commands.runbook_gates import run_generation_gates

    target = tmp_path / "syntax_target.py"
    target.write_text("x = 1\n", encoding="utf-8")
    content = _make_modify_runbook("syntax_target.py", "x = 1\n", "x = (\n")

    with (
        patch("agent.commands.runbook_gates.validate_runbook_schema", return_value=[]),
        patch("agent.commands.runbook_gates.validate_code_block", return_value=MagicMock(errors=[], warnings=[])),
        patch("agent.commands.runbook_gates.validate_sr_blocks", return_value=[]),
        patch("agent.commands.runbook_gates.check_impact_analysis_completeness", return_value=[]),
        patch("agent.commands.runbook_gates.check_adr_refs", return_value=[]),
        patch("agent.commands.runbook_gates.check_stub_implementations", return_value=[]),
        patch("agent.commands.runbook_gates.config") as gates_cfg,
        patch("agent.core.implement.loc_guard.config") as loc_cfg,
    ):
        gates_cfg.repo_root = tmp_path
        gates_cfg.max_correction_tokens = 10000
        loc_cfg.max_file_loc = 500
        _content, correction_parts, _gc, _nf, _delta = run_generation_gates(
            content=content, story_id="INFRA-176", story_content="Test",
            user_prompt="Generate", system_prompt="System",
            known_new_files=set(), attempt=1, max_attempts=5,
            gate_corrections=0, max_gate_corrections=3,
        )

    combined = "\n".join(correction_parts)
    assert correction_parts, "Expected at least one Gate 3.5 correction"
    assert "Gate 3.5" in combined
    assert "syntax_target.py" in combined
```

### Step 6: Deployment & Rollback Strategy

**Deployment Strategy**

The implementation of Gate 3.5 (Projected Syntax Validation) is strictly additive and side-effect free. It operates on in-memory projections of file contents during the runbook generation loop without modifying the working tree or any persistent state. Deployment is handled via the standard project merge process, and the check becomes active immediately upon the integration of the updated pipeline.

**Rollback Procedure**

Since the logic is decoupled from data persistence, rollback consists entirely of removing the gate call from the execution pipeline. No data migration or state cleanup is required.

**Manual Rollback Steps:**
1. Open `.agent/src/agent/commands/runbook_gates.py`.
2. Locate the `run_generation_gates` function.
3. Remove or comment out the block that invokes `check_projected_syntax` and extends `correction_parts`.

**Automated Rollback:**
A dedicated utility is provided to programmatically remove the gate from the pipeline if needed.

#### [NEW] .agent/src/agent/utils/rollback_infra_176.py

```python
"""Rollback utility for INFRA-176 syntax gate."""
import re
import sys
from pathlib import Path


def rollback_infra_176() -> None:
    """Removes the Gate 3.5 OTel span block from the runbook_gates pipeline."""
    gates_path = Path(".agent/src/agent/commands/runbook_gates.py")

    if not gates_path.exists():
        print(f"Error: {gates_path} not found.")
        sys.exit(1)

    content = gates_path.read_text(encoding="utf-8")

    # Match from the Gate 3.5 comment through the closing syn_span attribute,
    # inclusive — the entire `with tracer.start_as_current_span(...)` block.
    pattern = (
        r"\n    # Gate 3\.5: Projected Syntax Validation.*?"
        r'syn_span\.set_attribute\("gate35\.corrections"[^\n]*\)\n'
    )

    if not re.search(pattern, content, re.DOTALL):
        print("INFRA-176 gate block not found — no action needed.")
        return

    new_content = re.sub(pattern, "\n", content, flags=re.DOTALL)
    gates_path.write_text(new_content, encoding="utf-8")
    print("Successfully rolled back INFRA-176: Projected syntax gate removed.")


if __name__ == "__main__":
    rollback_infra_176()
```

**Troubleshooting Rollback**
If the automated rollback script fails to identify the pattern due to line-wrapping or formatting changes, manually verify the `run_generation_gates` sequence in `runbook_gates.py` and ensure `check_projected_syntax` is no longer being called. Removal of this call restores the generation loop behavior to its state prior to INFRA-176 exactly.

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
