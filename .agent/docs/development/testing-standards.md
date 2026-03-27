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