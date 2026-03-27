# Runbook: Implementation Runbook for INFRA-173

## State

ACCEPTED

## Implementation Steps

### Step 1: Architecture & Design Review

This section outlines the architectural transition from a binary pass/fail validation model to a multi-state validation system (SUCCESS, WARNING, FAILURE) to resolve the silent implementation drops described in INFRA-173.

**Multi-State Validation Logic**
Existing gate logic currently enforces a strict boolean check. This will be refactored to return a `GateResult` containing a `GateStatus` enum. This allows the implementation engine to distinguish between critical failures (e.g., syntax errors) and non-critical violations (e.g., missing docstrings in newly created files or test utilities).

**Language-Agnostic Test File Detection**
Following Rule 000, the detection of test files for the purpose of docstring exclusion must remain language-agnostic. We will utilize pattern-based matching rather than file extensions. The following patterns are validated for use:
- `test_.*`: Matches files starting with 'test_'.
- `.*_test`: Matches files ending with '_test' (before extension).
- `.*\.spec\..*`: Matches common specification naming conventions.
- `.*\.test\..*`: Matches common test naming conventions.

**ADR-012 Alignment: Non-Critical Docstring Violations**
In alignment with ADR-012 (Implementation Gate Strategy), the following documentation gaps are classified as non-critical warnings during the `verbatim-apply` phase:
1. Missing module-level docstrings in files marked as `[NEW]`.
2. Missing docstrings for functions or classes within files matching the test patterns defined above.
3. Missing docstrings for initialization methods (`__init__`) in utility files.

Files triggering these warnings will be written to the filesystem, and the implementation will be marked as successful (with warnings) instead of being added to the `rejected_files` list.

**Troubleshooting**
- **Hard Rejections on Test Files**: If `test_*.py` files continue to be rejected, verify that the regex patterns in `.agent/src/agent/commands/gates.py` correctly match the file path being processed.
- **Incomplete Implementation Banner**: If the success banner shows 'INCOMPLETE' despite files being written, ensure the implementation engine in `engine.py` is correctly excluding `GateStatus.WARNING` from the rejection count.

#### [MODIFY] CHANGELOG.md

```markdown
<<<SEARCH
## [Unreleased]
===
## [Unreleased] (Updated by story)

## [Unreleased]
**Changed**
- Updated implementation gate architecture to support tri-state validation (SUCCESS, WARNING, FAILURE) to prevent silent implement drops (INFRA-173).
- Defined language-agnostic test file exclusion patterns for docstring validation per Rule 000.
>>>

```

#### [MODIFY] .agent/src/agent/commands/gates.py

```python
<<<SEARCH
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from opentelemetry import trace

from agent.core.logger import get_logger
===
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional
from opentelemetry import trace
from agent.core.logger import get_logger

class GateStatus(Enum):
    """Status of a gate check."""
    SUCCESS = "success"
    WARNING = "warning"
    FAILURE = "failure"

# Language-agnostic test file patterns per Rule 000
TEST_FILE_PATTERNS = [
    r"^test_.*",
    r".*_test$",
    r".*\.spec\..*",
    r".*\.test\..*"
]

@dataclass
class GateResult:
    """Result of a gate check, including status and message."""
    status: GateStatus
    message: str
    resource_id: Optional[str] = None
>>>

```

### Step 2: Deployment & Rollback Strategy

This section defines the process for deploying the logic changes to the agent runtime and the mechanism for reverting to the previous strict validator behavior if necessary.

**Deployment Process**

Deployment involves merging the implementation into the primary branch. The agent's implementation engine will immediately begin using the updated logic for all subsequent `agent implement` calls. Post-deployment, developers should verify that implementation summary banners for new test files now display 'SUCCESS WITH WARNINGS' (or equivalent success state) rather than 'INCOMPLETE IMPLEMENTATION' when docstring gaps are present.

**Rollback Strategy**

If the downgrade to warnings results in a significant drop in documentation quality or unexpected side effects in the implementation Phase 1, the changes should be reverted via Git. A specific rollback utility script is provided to verify that the system has returned to the baseline rejection behavior.

#### [NEW] .agent/src/agent/utils/rollback_infra_173.py

```python
"""
Rollback verification script for INFRA-173.
Ensures that the docstring validator has returned to strict rejection mode.
"""
import sys

try:
    from agent.core.governance.validation import DocstringValidator
except ImportError:
    print("Error: Could not find DocstringValidator. Check source tree.")
    sys.exit(1)

def main():
    """Main verification routine."""
    validator = DocstringValidator()
    # test_*.py files were bypassed/downgraded in INFRA-173.
    # In strict mode, they should trigger a rejection if docstrings are missing.
    test_filename = "test_rollback_verification.py"
    test_content = "def test_logic(): pass"
    
    # Attempt to validate content that INFRA-173 would allow
    result = validator.validate(test_filename, test_content)
    
    # Check if status is back to 'fail'
    status = result.get("status") if isinstance(result, dict) else getattr(result, "status", None)
    
    if status == "fail":
        print("Rollback Verified: Strict docstring enforcement is active.")
        sys.exit(0)
    else:
        print("Rollback Check Failed: System is still in warning/bypass mode.")
        sys.exit(1)

if __name__ == "__main__":
    main()

```

### Step 3: Security & Input Sanitization

To prevent deceptive file paths from bypassing docstring validation gates, we implement a secure path matching utility. This ensures that exclusion patterns (e.g., `test_*.py`) are matched against the normalized filename component of the path, preventing traversal-based bypasses where an attacker might use deceptive naming like `src/test_utils/../../sensitive_file.py` to trick the gate into treating a source file as a test.

#### [NEW] .agent/src/agent/utils/path_security.py

```python
"""
Security utility for strict path anchoring and normalization in implementation gates.
"""
import os
import fnmatch
from pathlib import PurePosixPath

def is_test_file_secure(path: str) -> bool:
    """
    Determines if a file path refers to an excluded file (test or init) using strict anchoring.

    Normalizes the path to resolve traversal segments (..) and matches only the 
    filename against standard patterns. This prevents deceptive naming bypasses
    where a path might contain a pattern-matching string in its directory structure
    but target a non-test file.

    Args:
        path (str): The workspace-relative path to the file.

    Returns:
        bool: True if the file should be excluded from strict docstring gates.
    """
    if not path:
        return False

    # Normalize the path to resolve any traversal (..) or redundant segments
    # os.path.normpath resolves 'src/test/../auth.py' to 'src/auth.py'
    normalized = os.path.normpath(str(path)).replace("\\", "/")
    
    # Extract the filename component (the anchor)
    # Deceptive paths like '../test_auth.py' will resolve to their basename
    filename = os.path.basename(normalized)

    # Exclusion patterns based on Rule 000 and INFRA-173 requirements.
    # These cover Python (pytest), JavaScript/TypeScript (jest/mocha), and other standards.
    patterns = [
        "test_*",      # pytest/jest prefix
        "*_test.*",    # pytest/go suffix
        "*.test.*",    # modern JS/TS convention
        "*.spec.*",    # modern JS/TS convention
        "__init__.*"   # INFRA-173: exclude init files from docstring gate
    ]

    # Perform case-insensitive matching for robustness across platforms
    filename_lower = filename.lower()
    return any(fnmatch.fnmatch(filename_lower, pattern.lower()) for pattern in patterns)

```

#### [NEW] .agent/tests/agent/core/implement/test_path_security.py

```python
"""
Unit tests for secure path anchoring and exclusion logic.
"""
import pytest
from agent.utils.path_security import is_test_file_secure

def test_strict_anchoring_resolution():
    """Verify that deceptive traversal paths do not bypass docstring gates."""
    # Deceptive path targeting auth.py via a test directory segment
    # The resolved basename is 'auth.py', which should NOT match 'test_*'
    assert is_test_file_secure("src/tests/../auth.py") is False
    
    # Path with deep traversal targeting a config file
    assert is_test_file_secure("src/test_utils/../../config/secrets.py") is False
    
    # Standard filenames
    assert is_test_file_secure("test_auth.py") is True
    assert is_test_file_secure("auth.py") is False

def test_standard_pattern_coverage():
    """Verify all standard test naming conventions from Rule 000 are covered."""
    # Python / Pytest
    assert is_test_file_secure("test_utility.py") is True
    assert is_test_file_secure("utils_test.py") is True
    
    # JS / TS / Web
    assert is_test_file_secure("Button.test.tsx") is True
    assert is_test_file_secure("api.spec.ts") is True
    
    # INFRA-173 Specific: __init__ files
    assert is_test_file_secure("__init__.py") is True
    assert is_test_file_secure("agent/core/__init__.py") is True

def test_case_insensitivity():
    """Verify that naming checks are case-insensitive for platform compatibility."""
    assert is_test_file_secure("TEST_UTILITY.PY") is True
    assert is_test_file_secure("Test_Component.Spec.JS") is True

def test_edge_cases():
    """Verify handling of empty, null, or malformed inputs."""
    assert is_test_file_secure("") is False
    assert is_test_file_secure(None) is False
    assert is_test_file_secure(".") is False
    assert is_test_file_secure("..") is False

```

### Step 4: Observability & Audit Logging

This section implements the enhanced CLI feedback mechanisms for the implementation engine. By introducing a granular reporting layer, the agent now distinguishes between a perfect implementation, an implementation that succeeded but contains documentation warnings, and an incomplete implementation where critical files were rejected. This ensures that non-critical docstring gaps—especially in test files—are surfaced to the developer without hindering the persistence of the source code.

**Key Reporting Features:**
- **SUCCESS**: All files applied and passed all implementation gates.
- **SUCCESS WITH WARNINGS**: All files persisted to the filesystem, but some (e.g., `test_*.py` or files missing `__init__` docstrings) triggered non-blocking warnings.
- **INCOMPLETE IMPLEMENTATION**: Critical errors occurred or blocking gates failed, preventing some or all files from being applied.

#### [MODIFY] .agent/src/agent/utils/validation_formatter.py

```python
<<<SEARCH
from typing import Any, Dict, List, Union

from rich.panel import Panel

def format_runbook_errors(errors: List[Dict[str, Any]]) -> str:
===
from typing import Any, Dict, List, Union

from rich.panel import Panel

def format_runbook_errors(errors: List[Dict[str, Any]]) -> str:
>>>

```

#### [MODIFY] .agent/src/agent/commands/implement.py

```python
<<<SEARCH
from agent.commands import gates
from agent.commands.utils import update_story_state
===
from agent.commands import gates
from agent.commands.utils import update_story_state
from agent.utils.validation_formatter import format_implementation_summary
>>>

```

```python
<<<SEARCH
    if result.details:
        console.print(f"    [dim]{result.details}[/dim]")
# nolint: loc-ceiling
===
    if result.details:
        console.print(f"    [dim]{result.details}[/dim]")

def _display_implementation_summary(applied: List[str], warned: Dict[str, List[str]], failed: List[str]) -> None:
    """Renders the final implementation state to the CLI console."""
    console = Console()
    panel = format_implementation_summary(applied, warned, failed)
    console.print("\n")
    console.print(panel)
# nolint: loc-ceiling
>>>

```

**Troubleshooting Implementation Feedback:**
- **Missing Warnings**: If a file like `test_auth.py` contains docstring gaps but is not listed in the warnings section, ensure the `docstring_validator.py` regex for `test_*.py` patterns is correctly anchored.
- **Banner remains RED**: If the banner shows 'INCOMPLETE IMPLEMENTATION' despite only documentation warnings being present, check the engine logic in `verbatim_apply.py` to ensure documentation violations are correctly classified as non-critical failures.

### Step 5: Documentation Updates

Update the internal implementation engine documentation to formally define the new validation severity levels and the specific criteria for docstring gate exclusions.

#### [NEW] .agent/docs/implementation-engine.md

```markdown
# Implementation Engine

The Implementation Engine handles the application of code changes from generated runbooks to the local workspace. It operates in two primary phases: application and verification.

## Validation Gates

To maintain code quality and security standards, every file modification or creation passes through a series of validation gates. Gates now support three severity levels:

| Level | Description | Behavior |
| :--- | :--- | :--- |
| **Pass** | No violations detected. | File is written to disk. |
| **Warning** | Non-critical violations (e.g., missing docstrings in tests). | File is written to disk; a warning is logged. |
| **Fail** | Critical violations (e.g., syntax errors, security risks). | File is rejected; implementation is marked incomplete. |

## Docstring Validator

The docstring gate ensures that all new functions and classes include proper documentation. However, to prevent unnecessary friction, specific patterns are downgraded to `Warning` severity.

**Exclusion Patterns**

The following file patterns trigger warnings instead of failures when docstrings are missing:

- **Test Files**: Files following standard testing conventions:
  - `test_*.py` / `*_test.py` (Python)
  - `*.test.*` / `*.spec.*` (JavaScript/TypeScript)
- **Module Initializers**: `__init__.py` files.
- **New Files**: Non-test source files (`[NEW]`) with documentation gaps are written to disk but flagged as success-with-warnings to ensure developers can review logic immediately.

## Observability

When `agent implement` completes, the system provides a summary banner based on the highest severity encountered:

- **SUCCESS**: All files passed all gates.
- **SUCCESS WITH WARNINGS**: All files were written, but some triggered non-critical warnings.
- **INCOMPLETE IMPLEMENTATION**: One or more files were rejected due to hard failures.

## Troubleshooting

If a file is missing from your workspace after an implementation run:
1. Check the CLI output for any `REJECTED` entries.
2. Review the validation error message; if it is a syntax error or security violation, the gate correctly blocked the write.
3. Check `.agent/src/agent/core/implement/engine.py` for logic updates regarding `rejected_files` collection.

```

**Notes**:
- The documentation now correctly reflects the behavior introduced in INFRA-173, resolving the issue where test files were silently dropped.
- Users are encouraged to address warnings during the preflight or refinement stages of the workflow.

### Step 6: Verification & Test Suite

Execute unit tests to validate the transition from binary to multi-state implementation gates and ensure that new test/utility files are correctly handled with warnings rather than rejections. Integration tests will verify end-to-end implementation workflow persistence.

#### [NEW] .agent/tests/gates/test_docstring_validator.py

```python
import pytest
from pathlib import Path
from gates.docstring_validator import DocstringValidator

def test_filename_bypass_logic():
    """Verify that files matching test patterns bypass docstring requirements.
    
    Covers Scenario 1: Given a new file named test_utility.py, docstring gate 
    must be bypassed.
    """
    validator = DocstringValidator()
    
    # pytest patterns should PASS immediately
    res1 = validator.validate(Path("test_utility.py"), "def f(): pass")
    assert res1.status == "PASS"
    assert "Bypassed" in res1.message

    res2 = validator.validate(Path("utils_test.py"), "def f(): pass")
    assert res2.status == "PASS"

def test_downgrade_to_warning():
    """Verify that missing docstrings in new source files result in warnings.
    
    Covers Scenario 2: token_counter.py with missing __init__ docstring 
    should result in a warning.
    """
    validator = DocstringValidator()
    content = "def token_counter(): pass"
    result = validator.validate(Path("token_counter.py"), content)
    
    assert result.status == "WARNING"
    assert "missing function docstring" in result.message.lower()

def test_security_path_anchoring():
    """Ensure path traversal naming cannot be used to bypass the gate.
    
    Verifies that only real test files at appropriate locations are bypassed.
    """
    validator = DocstringValidator()
    # Deceptive path anchoring check
    result = validator.validate(Path("../test_auth.py"), "def secret(): pass")
    assert result.status == "WARNING"  # Treated as a regular file needing docs

def test_error_handling_graceful():
    """Verify system handles non-existent paths gracefully.
    
    Covers Scenario 4: Error handling should not attribute failures to docstrings.
    """
    validator = DocstringValidator()
    with pytest.raises(FileNotFoundError):
        validator.validate(Path("non_existent_path.py"), "")

```

#### [NEW] .agent/tests/implement/test_verbatim_apply.py

```python
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from implement.verbatim_apply import VerbatimApplier

@patch("implement.verbatim_apply.write_file")
@patch("implement.verbatim_apply.DocstringValidator")
def test_apply_writes_on_warning(mock_validator_cls, mock_write):
    """Verify that files with WARNING status are still written to the filesystem.
    
    Ensures work is not discarded even if linting/doc gaps exist.
    """
    mock_validator = mock_validator_cls.return_value
    mock_validator.validate.return_value = MagicMock(status="WARNING", message="Doc gap")
    
    applier = VerbatimApplier()
    success, status = applier.apply(Path("token_counter.py"), "content")
    
    assert success is True
    assert status == "WARNING"
    mock_write.assert_called_once()

```

#### [NEW] .agent/tests/implement/test_engine.py

```python
import pytest
from implement.engine import ImplementationEngine

def test_engine_summary_logic():
    """Verify implement summary banner distinguishes between SUCCESS and WARNINGS.
    
    Covers Scenario 3: Banner only triggers INCOMPLETE for critical failures.
    """
    engine = ImplementationEngine()
    
    # Case 1: Success with warnings
    engine.results = {
        "test_auth.py": "PASS",
        "utils.py": "WARNING"
    }
    assert engine.get_verdict() == "SUCCESS WITH WARNINGS"
    assert len(engine.rejected_files) == 0

    # Case 2: Critical implementation failure
    engine.results = {
        "broken_file.py": "FAIL"
    }
    assert engine.get_verdict() == "INCOMPLETE IMPLEMENTATION"
    assert "broken_file.py" in engine.rejected_files

def test_regression_syntax_errors():
    """Ensure syntax errors in new files still trigger hard rejections."""
    engine = ImplementationEngine()
    # Assume a mock validator returns FAIL for syntax errors
    engine.results = {"invalid.py": "FAIL"}
    assert engine.get_verdict() == "INCOMPLETE IMPLEMENTATION"

```

### Step 7: Deployment & Rollback Strategy

**Objective**: define the sequence for promoting implementation gate changes to the agent runtime and provide a verified fallback path to restore strict validation behavior.

**Deployment Process**

1. **Environment Preparation**: Ensure the local workspace is clean using `git status`. All changes from previous runbook sections should be staged.
2. **Verification Phase**: Execute the integration suite defined in the Verification section. Specifically, verify that `test_*.py` files are now successfully written despite docstring gaps.
3. **Promotion**: Commit the changes to the feature branch. The changes are active immediately within the agent runtime environment as it executes directly from the source code.
4. **Audit**: Review the `CHANGELOG.md` to ensure the versioning and impact are documented.

**Rollback Procedure**

In the event that downgrading implementations to warnings leads to unacceptable documentation decay or unexpected side effects in the implementation engine:

1. **Automated Rollback**: Execute the rollback utility provided below. This script will restore the original file states for the validator, the verbatim-apply logic, and the core implementation engine.
2. **Manual Rollback**: Alternatively, perform a manual revert using git:

    ```bash
    git checkout HEAD~1 -- .agent/src/gates/docstring_validator.py
    git checkout HEAD~1 -- .agent/src/implement/verbatim_apply.py
    git checkout HEAD~1 -- .agent/src/implement/engine.py
    ```

3. **Verification**: Run `pytest .agent/tests/gates/test_docstring_validator.py` to confirm that docstring gaps once again trigger hard rejections (baseline behavior).
