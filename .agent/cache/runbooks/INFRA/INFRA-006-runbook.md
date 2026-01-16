# Runbook: File-Based Versioning System (INFRA-006)

**Status**: ACCEPTED
**Story**: [INFRA-006](.agent/cache/stories/INFRA/INFRA-006-file-based-versioning-system.md)
**Assignee**: @Backend

## Context
The `agent` CLI currently relies on `git describe` for versioning. This fails when the tool is distributed as a tarball or installed in environments without `.git` metadata. We need a dual-strategy versioning system:
1.  **Dev/Git Mode**: Use `git describe` (dynamic).
2.  **Distribution Mode**: Use a static `VERSION` file generated at build time.

## Panel Review Findings

### @Architect
-   **Pattern**: The proposed pattern of "Dynamic fallback to Static" is standard for Python CLIs.
-   **Structure**: The `VERSION` file should live in the package root (e.g., inside `.agent/src/` or adjacent to `pyproject.toml`) so it is included in the build artifact.
-   **Dependency**: Ensure `package.sh` is the canonical way to build distribution artifacts.

### @Security
-   **Risk**: Low. Version strings are public information.
-   **Check**: Ensure the `VERSION` file isn't writable by the application at runtime (readonly).

### @QA
-   **Strategy**: Needs two distinct test cases:
    -   Case A: Running inside a git repo (mocks git command success).
    -   Case B: Running outside a git repo (mocks git failure, correct file read).
-   **Regression**: Ensure existing `--version` flag logic isn't broken.

### @Compliance
-   **Constraint**: No PII in version strings (standard git hashes are fine).

## Implementation Plan

### 1. Build Script Enhancement (`package.sh`)
-   **Objective**: Stamp the version during packaging.
-   **Changes**:
    -   Before running `tar`, execute: `git describe --tags --always --dirty > .agent/src/VERSION`.
    -   Ensure the `VERSION` file is included in the created archive.

### 2. Version Logic Update (`.agent/src/agent/version.py` or equivalent)
-   **Target File**: Likely `main.py` or a dedicated version utility.
-   **Logic**:
    ```python
    def get_version():
        # 1. Try Git
        try:
            return subprocess.check_output(["git", "describe", ...]).decode().strip()
        except:
            pass
        
        # 2. Try File
        version_file = Path(__file__).parent / "VERSION"  # Adjust path as needed
        if version_file.exists():
            return version_file.read_text().strip()
            
        # 3. Fallback
        return "unknown"
    ```

### 3. Verification Plan

#### Manual Verification
1.  **Git Context**: Run `agent --version` in current repo -> Verify output matches `git describe`.
2.  **No-Git Context**:
    -   Run `./package.sh`.
    -   Move `dist/agent-release.tar.gz` to `/tmp/`.
    -   Extract and run `./agent --version`.
    -   Verify it prints the version (not crash, not "unknown").

#### Automated Tests
-   Create `tests/core/test_version.py`.
-   Use `unittest.mock` to simulate `subprocess.check_output` raising `CalledProcessError`.
-   Verify correct fallback to file reading.
