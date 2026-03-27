# Runbook: Implementation Runbook for INFRA-171

## State

ACCEPTED

## Implementation Steps

### Step 1: Architecture & Design Review

This section confirms the architectural alignment of the Agent component with the project standard established in the Backend component (`backend/src/` and `backend/tests/`). We have identified exactly 49 orphaned functional test files within the `.agent/src/` hierarchy that are currently ignored by the test runner due to the `norecursedirs = ["src"]` configuration in `.agent/pyproject.toml`.

**Orphaned File Inventory (49 files):**
1. `.agent/src/agent/commands/tests/test_decompose_story.py` (and 8 others in same dir)
2. `.agent/src/agent/core/ai/tests/test_anthropic_provider.py` (and 8 others in same dir)
3. `.agent/src/agent/core/auth/tests/test_regression_credentials.py` (and 1 other in same dir)
4. `.agent/src/agent/core/implement/tests/test_assembly_benchmarks.py` (and 16 others in same dir)
5. `.agent/src/agent/core/tests/test_context_loader.py` (and 4 others in same dir)
6. `.agent/src/agent/sync/tests/test_bootstrap_discovery.py`
7. `.agent/src/agent/tools/tests/test_dynamic.py` (and 3 others in same dir)
8. `.agent/src/agent/core/preflight/test_healer.py`
9. `.agent/src/agent/sync/test_spacing.py`
10. `.agent/src/backend/voice/tools/custom/test_override.py` (Backend colocation edge case)

**Review Findings:**
- **Backend Alignment:** The backend structure correctly separates source and test. The Agent component will adopt a mirrored `.agent/tests/agent/...` structure.
- **Import Strategy:** Migrating these files from `.agent/src/agent/module/tests/test_x.py` to `.agent/tests/agent/module/test_x.py` necessitates refactoring all relative imports (e.g., `from ..module import Y`) to absolute repo-relative imports (e.g., `from agent.module import Y`).

#### [MODIFY] .agent/pyproject.toml

```toml
<<<SEARCH
[tool.pytest.ini_options]
norecursedirs = [
===
[tool.pytest.ini_options]
testpaths = ["tests"]
norecursedirs = [
>>>

```

#### [MODIFY] CHANGELOG.md

```markdown
<<<SEARCH
# Changelog
===
# Changelog

## [Unreleased] - INFRA-171
**Added**
- Explicit `testpaths` configuration in `.agent/pyproject.toml` to ensure discovery of consolidated tests.

**Changed**
- Identified 49 orphaned test files in `.agent/src/` for migration to top-level `.agent/tests/` directory.
>>>

```

**Troubleshooting:**
If `pytest` fails to discover tests after this change, verify that the `tests/` directory contains a valid `__init__.py` (it will be created in the next step). Note that functional tests remaining in `src` will remain invisible until moved, by design.

### Step 2: Implementation: Test Migration & Refactoring

This section handles the physical relocation of 49 test files and the necessary import refactoring to maintain test suite integrity. We use a dedicated migration script to ensure the regex-based refactoring of relative imports is applied consistently across all 49 files.

#### [NEW] .agent/scripts/migrate_tests.py

```python
import os
import re
from pathlib import Path
import shutil

# Source to Destination mapping mirroring the original hierarchy
MIGRATION_TARGETS = {
    ".agent/src/agent/commands/tests": ".agent/tests/agent/commands",
    ".agent/src/agent/core/ai/tests": ".agent/tests/agent/core/ai",
    ".agent/src/agent/core/auth/tests": ".agent/tests/agent/core/auth",
    ".agent/src/agent/core/implement/tests": ".agent/tests/agent/core/implement",
    ".agent/src/agent/sync/tests": ".agent/tests/agent/sync",
    ".agent/src/agent/tools/tests": ".agent/tests/agent/tools",
    ".agent/src/agent/core/tests": ".agent/tests/agent/core",
    ".agent/src/agent/core/preflight/test_healer.py": ".agent/tests/agent/core/preflight/test_healer.py"
}

def refactor_content(content: str, source_path: str) -> str:
    """Converts relative imports to absolute imports based on package location."""
    # Determine the absolute package prefix based on the source path
    # e.g., .agent/src/agent/commands/tests/test_x.py -> agent.commands
    parts = source_path.split('/')
    if 'agent' in parts:
        idx = parts.index('agent')
        # Get parts between 'agent' and 'tests'
        pkg_sub = parts[idx:parts.index('tests')] if 'tests' in parts else parts[idx:-1]
        absolute_prefix = ".".join(pkg_sub)
        
        # Replace 'from ..module' with 'from absolute_prefix.module'
        content = re.sub(r'from \.\.([\w\.]+)', f'from {absolute_prefix}.\\1', content)
        # Replace 'from .module' (if used inside the old tests dir) with 'from absolute_prefix.tests.module'
        # Though standard is to point to source.
    return content

def migrate():
    count = 0
    for src, dst in MIGRATION_TARGETS.items():
        src_path = Path(src)
        dst_path = Path(dst)
        
        if src_path.is_file():
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            content = src_path.read_text()
            new_content = refactor_content(content, str(src_path))
            dst_path.write_text(new_content)
            src_path.unlink()
            count += 1
        elif src_path.is_dir():
            dst_path.mkdir(parents=True, exist_ok=True)
            for test_file in src_path.glob("test_*.py"):
                rel_name = test_file.name
                target = dst_path / rel_name
                content = test_file.read_text()
                new_content = refactor_content(content, str(test_file))
                target.write_text(new_content)
                test_file.unlink()
                count += 1
            # Remove original directory if empty or contains only __init__.py
            for init_file in src_path.glob("__init__.py"):
                init_file.unlink()
            if not any(src_path.iterdir()):
                src_path.rmdir()
    
    print(f"Successfully migrated {count} files.")

if __name__ == "__main__":
    migrate()

```

#### [DELETE] .agent/src/agent/commands/tests/\_\_init\_\_.py
rationale: Core test logic migrated to consolidated .agent/tests/ directory to ensure discovery by pytest.

#### [DELETE] .agent/src/agent/core/ai/tests/\_\_init\_\_.py
rationale: AI provider tests migrated to consolidated .agent/tests/ structure per ADR-012.

#### [DELETE] .agent/src/agent/core/implement/tests/\_\_init\_\_.py
rationale: Implementation engine tests relocated to top-level tests directory to resolve orphaned status.

#### [DELETE] .agent/src/agent/tools/tests/\_\_init\_\_.py
rationale: Tooling unit tests relocated; directory removed to enforce src/tests separation.

#### [DELETE] .agent/src/agent/sync/tests/\_\_init\_\_.py
rationale: Sync discovery tests moved to .agent/tests/agent/sync/.

**Refactoring Execution**

1. Run the migration script: `python .agent/scripts/migrate_tests.py`.
2. This script automatically handles the 49 identified files, transforming relative imports (e.g., `from ..stop importstop`) into absolute ones (e.g., `from agent.commands.stop import stop`).
3. Verify that all `tests/` subdirectories within `.agent/src/` have been removed.

**Troubleshooting**
- **ImportError**: If a migrated test fails with an ImportError, verify the `absolute_prefix` logic in the script correctly mapped the directory level. For example, tests in `core/ai/` should import production code from `agent.core.ai`.
- **Empty Modules**: If `pytest` complains about empty modules, ensure the `__init__.py` files were created in the destination if they are required for namespace package discovery (though modern pytest usually handles this without them).

### Step 3: Implementation: Policy & Prompt Enforcement

Objective: Standardize the codebase by strictly forbidding colocated tests through both architectural rules and AI prompt guardrails. This ensures all tests are discoverable by pytest, which is configured to ignore the `src/` directory for test discovery.

#### [MODIFY] .agent/rules/400-lean-code.mdc

```

<<<SEARCH
### Test Directory Structure (MANDATORY)
- Test files MUST live in a dedicated `tests/` directory at the **same level** as `src/`, NEVER inside `src/`.
- The canonical pattern is: `<component>/src/` for source code, `<component>/tests/` for tests.
- Examples:
  - `.agent/src/agent/core/ai/` -> `.agent/tests/core/ai/`
  - `backend/src/` -> `backend/tests/`
- Do NOT create `tests/` subdirectories inside any `src/` package.
- Test files may mirror the source hierarchy but must be rooted under the top-level `tests/` directory.
- This rule applies to ALL code this project generates or manages, including runbook `[NEW]` blocks.
===
**Test Directory Structure (MANDATORY)**
- Test files MUST live in a dedicated `tests/` directory at the **same level** as `src/`, NEVER inside `src/`. **Colocated tests are strictly forbidden.**
- **Rationale**: The `pyproject.toml` configuration sets `norecursedirs=["src"]`, meaning tests placed inside `src/` hierarchies are orphaned and will never be executed by CI/CD.
- The canonical pattern is: `<component>/src/` for source code, `<component>/tests/` for tests.
- Examples:
  - `.agent/src/agent/core/ai/` -> `.agent/tests/core/ai/`
  - `backend/src/` -> `backend/tests/`
- Do NOT create `tests/` subdirectories inside any `src/` package. Any such directories found during review MUST result in a BLOCK.
- Test files may mirror the source hierarchy but must be rooted under the top-level `tests/` directory.
- This rule applies to ALL code this project generates or manages, including runbook `[NEW]` blocks.
>>>

```

#### [MODIFY] .agent/src/agent/core/ai/prompts.py

```python
<<<SEARCH
CRITICAL FILE ASSIGNMENT RULE:
Each file path MUST appear in exactly ONE section's "files" list.
If multiple sections need to modify the same file, consolidate ALL changes for
that file into a SINGLE section. This prevents cascading search/replace conflicts
where later sections search for text that earlier sections already changed.
===
CRITICAL FILE ASSIGNMENT RULE:
Each file path MUST appear in exactly ONE section's "files" list.
If multiple sections need to modify the same file, consolidate ALL changes for
that file into a SINGLE section. This prevents cascading search/replace conflicts
where later sections search for text that earlier sections already changed.

TEST FILE PLACEMENT RULE:
Test files MUST be assigned to the top-level `tests/` directory mirroring the 
source hierarchy (e.g., `.agent/tests/...`). NEVER place tests inside a `src/` directory.
>>>
<<<SEARCH
12. TEST PLACEMENT: Test files MUST be placed in the top-level `tests/` directory,
    NEVER inside `src/`. The pattern is `<component>/tests/` mirroring the source structure.
    Example: tests for `.agent/src/agent/core/ai/` go in `.agent/tests/core/ai/`.
    Do NOT create `[NEW] .agent/src/**/tests/` paths.
===
12. TEST PLACEMENT: Test files MUST be placed in the top-level `tests/` directory,
    NEVER inside `src/`. Colocated tests are strictly forbidden as they are ignored by the test runner.
    The pattern is `<component>/tests/` mirroring the source structure.
    Example: tests for `.agent/src/agent/core/ai/` go in `.agent/tests/agent/core/ai/`.
    Do NOT create `[NEW] .agent/src/**/tests/` paths.
>>>

```

**Troubleshooting**
- If the MDC rule does not trigger in Cursor, ensure that the `.mdc` file is properly indexed and that the `alwaysApply` flag is set to true.
- If AI-generated runbooks still attempt to colocate tests, verify that the `prompts.py` changes have been reloaded by the agent service.

### Step 4: Security & Input Sanitization

Verify that the automated migration did not inadvertently commit sensitive developer information or hardcoded absolute paths from the local environments where tests were originally authored. This step ensures that consolidated verification code remains compliant with SOC 2 data handled standards.

#### [NEW] .agent/src/agent/core/governance/migration_audit_tool.py

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

"""Utility to verify that migrated test files are sanitized of local PII and credentials."""

import re
import os
from pathlib import Path
from typing import List, Tuple

# Common patterns for leaked local data or credentials
AUDIT_PATTERNS = {
    "OpenAI Key": r"sk-[a-zA-Z0-9]{48}",
    "Google API Key": r"AIza[0-9A-Za-z-_]{35}",
    "Anthropic Key": r"sk-ant-api03-[a-zA-Z0-9-_]{93}",
    "Local Home Path (Unix)": r"/Users/[a-zA-Z0-9._-]+",
    "Local Home Path (Windows)": r"[a-zA-Z]:\\Users\\[a-zA-Z0-9._-]+",
    "Generic Password Variable": r'(?i)password\s*=\s*["\'][^"\']{4,}["\']'
}

def run_security_audit(target_dir: str = ".agent/tests") -> List[Tuple[str, str, str]]:
    """
    Scans all files in target_dir for sensitive patterns.
    
    Returns:
        List of (file_path, pattern_name, match_text)
    """
    findings = []
    root = Path(target_dir)
    
    if not root.exists():
        return []

    for py_file in root.rglob("*.py"):
        content = py_file.read_text()
        for name, pattern in AUDIT_PATTERNS.items():
            matches = re.findall(pattern, content)
            for match in matches:
                findings.append((str(py_file), name, match))
                
    return findings

if __name__ == "__main__":
    print("Starting Security Audit of migrated tests...")
    results = run_security_audit()
    if not results:
        print("✅ No sensitive data or local paths detected in migrated files.")
    else:
        print(f"❌ Found {len(results)} potential security violations:")
        for file, ptype, match in results:
            print(f"  - {file}: {ptype} detected")
        exit(1)

```

**Troubleshooting**
- If the audit tool flags a `Local Home Path`, verify if the path is a legitimate fixture or a leaked environment variable. Mock paths should use generic placeholders like `/tmp/agent_tests/` instead of actual user directories.
- Ensure `pytest` execution logs in CI are checked for absolute path leakage by verifying that the `rootdir` in the OTel spans remains relative to the workspace root.

### Step 5: Observability & Audit Logging

To ensure full transparency during the test consolidation and confirm the successful discovery of migrated test files by the CI/CD runner, we establish a metrics baseline and a recurring validation tool.

#### [NEW] .agent/src/agent/core/governance/test_metrics.py

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

"""Utility to establish test baselines and verify discovery delta post-migration."""

import subprocess
import json
import os
import sys
from datetime import datetime

def run_pytest_collection():
    """Collects tests via pytest and returns count of items discovered."""
    # Query pytest collection without executing tests to establish discovery count
    result = subprocess.run(
        ["pytest", "--collect-only", "-q"],
        capture_output=True,
        text=True
    )
    for line in result.stdout.splitlines():
        if "collected" in line and "items" in line:
            try:
                # Standard pytest output: "collected X items"
                return int(line.split(' ')[1])
            except (IndexError, ValueError):
                continue
    return 0

def get_orphaned_src_tests():
    """Identifies any test directories remaining inside the src/ hierarchy."""
    orphans = []
    for root, dirs, _ in os.walk(".agent/src"):
        if "tests" in dirs:
            orphans.append(os.path.join(root, "tests"))
    return orphans

def main():
    """Main execution for observability metrics."""
    metrics = {
        "timestamp": datetime.utcnow().isoformat(),
        "total_tests_discovered": run_pytest_collection(),
        "orphaned_src_directories": get_orphaned_src_tests(),
        "discovery_path": ".agent/tests/",
        "status": "PENDING"
    }
    
    # Determine status based on architectural standards
    if metrics["orphaned_src_directories"]:
        metrics["status"] = "FAIL: Colocated tests detected in src/"
    else:
        metrics["status"] = "PASS"
        
    print(json.dumps(metrics, indent=2))
    
    if metrics["orphaned_src_directories"]:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()

```

**Metrics & Baseline Strategy**

1. **Establish Baseline**: Before executing the migration, run `python .agent/src/agent/core/governance/test_metrics.py`. Record the `total_tests_discovered`. Because the current `.agent/pyproject.toml` excludes the `src` directory from recursion, this count represents only a subset of intended tests.
2. **Verify discovery Delta**: Immediately following the migration of the 49 test files to `.agent/tests/`, re-run the metrics tool. The `total_tests_discovered` count MUST increase by exactly the number of files migrated (minus any that were previously discovered via explicit path targeting).
3. **CI/CD Integration**: Integrate this script into the pipeline pre-test phase. Ensure that `orphaned_src_directories` is empty; if the list is populated, the build must fail to prevent architectural drift.

**Troubleshooting Discovery Failures**

- **No Increase in Test Count**: If the discovery count remains static after migration, verify that the `norecursedirs` list in `.agent/pyproject.toml` (modified in Step 1) correctly omitted `tests` while retaining `src` exclusion.
- **ImportErrors during Collection**: If pytest fails to collect items due to `ModuleNotFoundError`, check that the absolute imports refactored in Step 2 match the `agent.*` package structure.
- **Permissions**: Ensure the script has read access to the `.agent/tests` hierarchy.

### Step 6: Documentation Updates

Update the project documentation to formalize the architectural requirement for the separation of source code and test code. This ensures all developers and AI agents adhere to the consolidated directory structure, preventing orphaned tests and maintaining codebase hygiene.

#### [NEW] .agent/docs/development/testing-standards.md

~~~markdown
# Testing Standards: Source and Test Separation

## Overview

To ensure maintainability, clear dependency boundaries, and reliable test discovery, this project enforces a strict separation between production source code (`src/`) and test code (`tests/`). Colocating test files within source packages is strictly forbidden.

## Directory Structure

Every component must follow the top-level separation pattern. Tests should never be placed inside a `src/` or package directory.

**Canonical Pattern**

- **Source Root**: `<component>/src/` (e.g., `.agent/src/agent/` or `backend/src/`)
- **Test Root**: `<component>/tests/` (e.g., `.agent/tests/` or `backend/tests/`)

**Hierarchy Mirroring**

Test files must mirror the package structure of the source code they verify. This makes it intuitive to locate tests for any given module.

| Source Path | Canonical Test Path |
|-------------|---------------------|
| `.../src/package/module.py` | `.../tests/package/test_module.py` |
| `.../src/package/sub/logic.py` | `.../tests/package/sub/test_logic.py` |

## Component Examples

**Agent Component**

Production code for the AI service is located in the core package. The tests reside in the mirrored path under the global agent tests directory.

- **Source**: `.agent/src/agent/core/ai/service.py`
- **Test**: `.agent/tests/agent/core/ai/test_service.py`

**Backend Component**

Backend services follow the same pattern at the root of the `backend/` directory.

- **Source**: `backend/src/voice/orchestrator.py`
- **Test**: `backend/tests/voice/test_orchestrator.py`

## Mandatory Rules

1.  **No `tests/` in `src/`**: Creating a directory named `tests` inside any hierarchy starting with `src/` is a violation of Rule 400 (Lean Code) and will trigger a governance block.
2.  **Absolute Imports**: Tests must use absolute imports to reference the modules under test. Do not use relative imports (e.g., `from ..module`).
    - **Correct**: `from agent.core.ai.service import AIService`
    - **Incorrect**: `from ..service import AIService`
3.  **Discovery Compliance**: The `pyproject.toml` configuration sets `norecursedirs = ["src"]`. Tests placed inside `src/` will be ignored by the test runner, leading to silent regressions.

## Enforcement

- **Static Analysis**: Cursor Rule `400-lean-code.mdc` automatically flags colocated test directories.
- **Preflight Checks**: The `/preflight` command validates that all new tests are discovered in the canonical `tests/` path.
~~~

**Troubleshooting**

If tests are not being discovered after migration:
1. Verify that the file name starts with `test_` or ends with `_test.py`.
2. Ensure the parent directory in `.agent/tests/` does not contain an `__init__.py` if you want `pytest` to treat it as a directory of independent test modules rather than a package (though mirroring the source package structure is usually preferred).
3. Check `.agent/pyproject.toml` to ensure the new directory isn't explicitly excluded in `norecursedirs`.

### Step 7: Verification & Test Suite

Verify that all 49 migrated test files are correctly discovered by pytest and that the new architectural boundary is enforced by the Lean Code MDC rule.

#### [NEW] .agent/tests/agent/core/governance/test_migration_verification.py

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

```

~~~
### Step 8: Deployment & Rollback Strategy

This section outlines the sequence for deploying the test consolidation and the procedure for reverting to the previous state using Git and a custom recovery utility.

**Deployment Procedure**

1. **Pre-flight Baseline**: Execute the discovery metrics tool to record the current state:
   ```bash
   python .agent/src/agent/core/governance/test_metrics.py
   ```

1. **Migration Execution**: Execute the migration script to move 49 test files and refactor relative imports to absolute imports:

   ```bash
   python .agent/scripts/migrate_tests.py
   ```

2. **Post-migration Verification**: Execute the full test suite and validation tools:

   ```bash
   pytest .agent/tests/
   python .agent/src/agent/core/governance/migration_audit_tool.py
   pytest .agent/tests/agent/core/governance/test_migration_verification.py
   ```

3. **Commit & Push**: Once all verification tests pass and import resolution is confirmed, stage and commit the changes.

**Rollback Procedure**

If catastrophic import failures occur or the consolidated structure causes environment-specific discovery loops:

1. **Git Revert**: Revert all file movements and configuration changes using Git:

   ```bash
   git checkout HEAD .agent/src/ .agent/tests/ .agent/pyproject.toml .agent/rules/400-lean-code.mdc .agent/src/agent/core/ai/prompts.py
   ```

2. **Artifact Cleanup**: Remove the temporary implementation and documentation files created during the migration process:

   ```bash
   rm .agent/scripts/migrate_tests.py
   rm .agent/src/agent/core/governance/migration_audit_tool.py
   rm .agent/src/agent/core/governance/test_metrics.py
   rm .agent/docs/development/testing-standards.md
   rm .agent/tests/agent/core/governance/test_migration_verification.py
   ```

3. **Sanity Check**: Execute `pytest`. The runner should only discover tests in the original `.agent/tests/` hierarchy (skipping colocated `tests/` folders in `src/` as per the restored `norecursedirs` config).

Alternatively, use the following automated rollback script to perform these operations.

#### [NEW] .agent/src/agent/utils/rollback_infra_171.py

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

"""Contingency utility to revert INFRA-171 migration changes and cleanup implementation artifacts."""

import subprocess
import sys
from pathlib import Path

# Files to be reverted to HEAD state
REVERT_TARGETS = [
    ".agent/src",
    ".agent/tests",
    ".agent/pyproject.toml",
    ".agent/rules/400-lean-code.mdc",
    ".agent/src/agent/core/ai/prompts.py"
]

# Temporary artifacts to delete
CLEANUP_TARGETS = [
    ".agent/scripts/migrate_tests.py",
    ".agent/src/agent/core/governance/migration_audit_tool.py",
    ".agent/src/agent/core/governance/test_metrics.py",
    ".agent/docs/development/testing-standards.md",
    ".agent/tests/agent/core/governance/test_migration_verification.py"
]

def run_rollback():
    """Executes git checkout and removes implementation files."""
    print("Starting rollback of INFRA-171...")

    # 1. Git checkout revert
    try:
        subprocess.run(["git", "checkout", "HEAD", "--"] + REVERT_TARGETS, check=True)
        print("✅ Successfully restored src, tests, and configuration from Git HEAD.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during git checkout: {e}")
        sys.exit(1)

    # 2. Cleanup artifacts
    for target in CLEANUP_TARGETS:
        path = Path(target)
        if path.exists():
            try:
                if path.is_file():
                    path.unlink()
                    print(f"🗑️ Removed artifact: {target}")
            except OSError as e:
                print(f"⚠️ Failed to remove {target}: {e}")

    print("Rollback complete. System state restored.")

if __name__ == "__main__":
    run_rollback()

```
