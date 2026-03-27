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

import os
from pathlib import Path
import pytest

"""Programmatic verification of INFRA-171 test consolidation."""

def test_no_colocated_tests_in_src():
    """Verify that no directory named 'tests' exists anywhere within the src hierarchy."""
    src_root = Path(".agent/src")
    violations = []
    for root, dirs, files in os.walk(src_root):
        if "tests" in dirs:
            violations.append(os.path.join(root, "tests"))
    
    assert not violations, f"Architectural Violation: Colocated tests found at {violations}"

def test_test_discovery_count():
    """Verify that pytest discovers the expected hierarchy under .agent/tests."""
    test_root = Path(".agent/tests/agent")
    # We expect at least the migrated subdirectories to exist and contain files
    required_dirs = ["commands", "core/ai", "core/auth", "core/implement", "sync", "tools"]
    for d in required_dirs:
        full_path = test_root / d
        assert full_path.is_dir(), f"Missing consolidated test directory: {full_path}"
        # Ensure it's not empty (should contain test_*.py files)
        files = list(full_path.glob("test_*.py"))
        assert len(files) > 0, f"No tests discovered in {full_path}"

def test_absolute_import_resolution():
    """Verify that absolute imports for the agent package are functional post-migration."""
    try:
        from agent.core.utils import scrub_sensitive_data
        from agent.commands.decompose_story import get_next_ids
        assert scrub_sensitive_data is not None
        assert get_next_ids is not None
    except ImportError as e:
        pytest.fail(f"Absolute import failed: {e}. Migration refactoring may be incomplete.")

~~~

**Verification Steps**

1. **Execute Full Test Suite**:
   Confirm that `pytest` now executes the migrated tests. Run from the repository root:
   ```bash
   pytest .agent/tests
   ```

   Confirm that the total number of tests passed includes the 49 migrated files.

1. **Run Observability Metrics**:
   Validate the system state using the tool created in Step 5:

   ```bash
   python3 .agent/src/agent/core/governance/test_metrics.py
   ```

   The output must return `"status": "PASS"`. If it returns `"FAIL"`, use the list of `orphaned_src_directories` in the JSON response to manually clean up missed `tests/` folders.

2. **MDC Rule Validation (Negative Test)**:
   To verify that the AI Governance Panel and Cursor correctly block future violations:
   - Attempt to create a file at `.agent/src/agent/core/tests/violation.py`.
   - **Expected Outcome**: The editor must flag a violation of Rule 400 (Lean Code), specifically citing the "Test Directory Structure (MANDATORY)" section which forbids `tests/` inside `src/`.

3. **Security Audit Check**:
   Final check for accidental credential leakage in the test code:

   ```bash
   python3 .agent/src/agent/core/governance/migration_audit_tool.py
   ```

**Troubleshooting**
- **ModuleNotFoundError**: Ensure your `PYTHONPATH` includes `.agent/src`. If running via `uv`, use `uv run pytest .agent/tests`.
- **Discovery Warnings**: If `pytest` warns about "cannot collect test class", ensure that the migration script correctly removed all `__init__.py` files from the source directories (colocated tests must not be Python packages if we want to avoid import collisions).
- **MDC Not Triggering**: Ensure the `.agent/rules/400-lean-code.mdc` file is correctly formatted and recognized by the IDE. Verify that the `globs` in the rule include the path you are testing.
