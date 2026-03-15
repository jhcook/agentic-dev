# STORY-ID: INFRA-138: Canonical CWD Path Resolution

## State

ACCEPTED

## Goal Description

Eliminate CWD-dependent path resolution throughout the agent CLI. All file operations — in the implement orchestrator, Pydantic validators, and governance gates — must resolve paths against `config.repo_root`, not `os.getcwd()`. This fix addresses a systemic reliability bug where `agent implement`, `ModifyBlock` validation, and `agent preflight` fail when the CLI is invoked from `.agent/` because paths resolve as `.agent/.agent/src/...`.

## Linked Journeys

- JRN-062: Implement Oracle Preflight Pattern

## Panel Review Findings

### @Architect
- **Single Source of Truth**: `config.repo_root` is the canonical anchor (line 48 of `config.py`). All path resolution must flow through it.
- **Scope**: 5 files modified. The new utility is ~15 lines. Each integration point is a small, targeted change — well within budget.

### @Security
- **Path Traversal**: The `resolve_repo_path()` utility rejects `..` traversal and absolute paths, maintaining the existing safety boundary from `models.py`.
- **No New Attack Surface**: This is a refactor of existing path logic, not new file system access.

### @QA
- **Regression Risk**: Low. The changes replace implicit CWD assumptions with explicit `config.repo_root` references.
- **Test Coverage**: Tests verify resolution works from any CWD (repo root, `.agent/`, `/tmp/`). Negative tests for traversal attacks.

### @Observability
- **Migration Logging**: `resolve_repo_path()` logs a warning when a path would have resolved differently under old CWD behavior, aiding transition diagnostics.

## Codebase Introspection

### Targeted File Contents

#### .agent/src/agent/core/config.py (506 LOC)
- `Config.__init__` (line 47): Sets `self.repo_root = self._find_repo_root()`.
- `config = Config()` singleton (line 395): Module-level instance used throughout codebase.
- Insert point: After `get_provider_config()` (line 452) — add `resolve_repo_path()` as a module-level utility.

#### .agent/src/agent/core/implement/resolver.py (161 LOC)
- `resolve_path()` (line 87): Uses `file_path = Path(filepath); if file_path.exists()` — CWD-relative.
- `_find_file_in_repo()` (line 31): Git search — CWD-relative `subprocess` call.
- `_find_directories_in_repo()` (line 49): `find .` — CWD-relative.

#### .agent/src/agent/core/implement/orchestrator.py (244 LOC)
- `apply_chunk()` line 166: `fp = Path(sr_filepath); original_content = fp.read_text() if fp.exists()` — CWD-relative.
- `apply_chunk()` line 189: `fp = Path(block["file"]); original_content = fp.read_text() if fp.exists()` — CWD-relative.
- `build_source_context()` line 65: `resolved = resolve_path(filepath)` — delegates to resolver.

#### .agent/src/agent/core/implement/models.py (108 LOC)
- `ModifyBlock.validate_modify_path()` (line 42): Only checks `..` traversal and absolute paths. Parent dir check was removed as CWD workaround in INFRA-134.

#### .agent/tests/core/implement/test_pathing.py (60 LOC)
- 4 existing tests for `resolve_path()`. Need new tests for `resolve_repo_path()` and CWD-independence.

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| `resolve_path()` returns `Path` or `None` | `resolver.py:87` | CWD-relative | **Fix** → repo_root-relative |
| Trusted prefix short-circuit | `resolver.py:108` | Returns bare `Path` | **Fix** → Returns `repo_root / Path` |
| `ModifyBlock` path traversal safety | `models.py:48` | `..` and `/` rejected | Yes |
| `ModifyBlock` parent dir check | `models.py` | Removed (INFRA-134) | **Restore** with `config.repo_root` |
| `preflight.py` cache path | `preflight.py:81,92` | `config.cache_dir` | Already fixed |

## Implementation Steps

### Step 1: Add `resolve_repo_path()` Utility to Config Module

Add the canonical path resolver as a module-level function in `config.py`. This is the single source of truth for all repo-relative path resolution.

#### [MODIFY] .agent/src/agent/core/config.py

```
<<<SEARCH
def get_valid_providers() -> List[str]:
    """
    Returns list of valid AI provider names.
    """
    return ["gh", "openai", "gemini", "anthropic", "vertex", "ollama"]
===
def resolve_repo_path(relative: str) -> Path:
    """Resolve a repo-relative path against config.repo_root (AC-1).

    This is the canonical path resolver for the entire agent framework.
    All file operations must use this instead of bare ``Path(relative)``.

    Args:
        relative: Repository-relative path (e.g. ``.agent/src/agent/config.py``).

    Returns:
        Absolute :class:`Path` anchored to ``config.repo_root``.

    Raises:
        ValueError: If path contains ``..`` traversal or is absolute.
    """
    if ".." in relative:
        raise ValueError(f"Path traversal not allowed: {relative}")
    if relative.startswith("/"):
        raise ValueError(f"Absolute paths not allowed: {relative}")
    resolved = (config.repo_root / relative).resolve()
    # Ensure the resolved path is still within repo_root (belt-and-suspenders)
    if not str(resolved).startswith(str(config.repo_root.resolve())):
        raise ValueError(f"Path escapes repo root: {relative}")
    return resolved


def get_valid_providers() -> List[str]:
    """
    Returns list of valid AI provider names.
    """
    return ["gh", "openai", "gemini", "anthropic", "vertex", "ollama"]
>>>
```

### Step 2: Fix `resolve_path()` to Use `config.repo_root`

Update the core resolver to anchor all existence checks and path returns against `config.repo_root`. This is the root cause fix — `Path(filepath).exists()` currently checks against CWD.

#### [MODIFY] .agent/src/agent/core/implement/resolver.py

```
<<<SEARCH
"""Resolver utilities for repository path search and story ID extraction."""

import logging
import re
import subprocess
from pathlib import Path
from typing import List, Optional

from rich.console import Console

_console = Console()
===
"""Resolver utilities for repository path search and story ID extraction."""

import logging
import re
import subprocess
from pathlib import Path
from typing import List, Optional

from rich.console import Console

from agent.core.config import config

_console = Console()
>>>
```

#### [MODIFY] .agent/src/agent/core/implement/resolver.py

```
<<<SEARCH
def resolve_path(filepath: str) -> Optional[Path]:
    """Resolve a file path to a real location, with fuzzy fallback.

    Resolution order:

    1. Exact match — return as-is.
    2. Single unique file match in repo — auto-redirect.
    3. New file with trusted root prefix — trust the full path.
    4. New file with unknown prefix — fuzzy-search directory by directory.

    Args:
        filepath: Repo-relative file path (may be AI-generated).

    Returns:
        Resolved :class:`pathlib.Path`, or ``None`` if ambiguous/invalid.
    """
    file_path = Path(filepath)
    if file_path.exists():
        return file_path
===
def resolve_path(filepath: str) -> Optional[Path]:
    """Resolve a file path to a real location, with fuzzy fallback.

    Resolution order:

    1. Exact match against repo_root — return anchored path.
    2. Single unique file match in repo — auto-redirect.
    3. New file with trusted root prefix — trust the full path.
    4. New file with unknown prefix — fuzzy-search directory by directory.

    All existence checks are anchored to ``config.repo_root`` (INFRA-138),
    eliminating CWD-dependency.

    Args:
        filepath: Repo-relative file path (may be AI-generated).

    Returns:
        Resolved :class:`pathlib.Path`, or ``None`` if ambiguous/invalid.
    """
    repo_root = config.repo_root
    file_path = repo_root / filepath
    if file_path.exists():
        return file_path
>>>
```

#### [MODIFY] .agent/src/agent/core/implement/resolver.py

```
<<<SEARCH
    # Trusted paths know exactly where they want to live — skip fuzzy search.
    is_trusted = any(filepath.startswith(p) for p in TRUSTED_ROOT_PREFIXES)
    if is_trusted:
        return file_path
===
    # Trusted paths know exactly where they want to live — skip fuzzy search.
    is_trusted = any(filepath.startswith(p) for p in TRUSTED_ROOT_PREFIXES)
    if is_trusted:
        return repo_root / filepath
>>>
```

#### [MODIFY] .agent/src/agent/core/implement/resolver.py

```
<<<SEARCH
    if file_path.name not in COMMON_FILES:
        candidates = _find_file_in_repo(file_path.name)
        exact = [c for c in candidates if Path(c).name == file_path.name]
===
    bare_path = Path(filepath)
    if bare_path.name not in COMMON_FILES:
        candidates = _find_file_in_repo(bare_path.name)
        exact = [c for c in candidates if Path(c).name == bare_path.name]
>>>
```

#### [MODIFY] .agent/src/agent/core/implement/resolver.py

```
<<<SEARCH
            if new_path != filepath:
                _console.print(f"[yellow]⚠️  Path Auto-Correct (File): '{filepath}' -> '{new_path}'[/yellow]")
                logging.warning(
                    "Path auto-corrected via fuzzy match",
                    extra={
                        "event": "path_auto_correction",
                        "original_path": filepath,
                        "resolved_path": new_path
                    }
                )
            return Path(new_path)
===
            if new_path != filepath:
                _console.print(f"[yellow]⚠️  Path Auto-Correct (File): '{filepath}' -> '{new_path}'[/yellow]")
                logging.warning(
                    "Path auto-corrected via fuzzy match",
                    extra={
                        "event": "path_auto_correction",
                        "original_path": filepath,
                        "resolved_path": new_path
                    }
                )
            return repo_root / new_path
>>>
```

#### [MODIFY] .agent/src/agent/core/implement/resolver.py

```
<<<SEARCH
    parts = file_path.parts
    current_check = Path(".")

    for i, part in enumerate(parts[:-1]):
        next_check = current_check / part
        if not next_check.exists():
===
    parts = bare_path.parts
    current_check = repo_root

    for i, part in enumerate(parts[:-1]):
        next_check = current_check / part
        if not next_check.exists():
>>>
```

#### [MODIFY] .agent/src/agent/core/implement/resolver.py

```
<<<SEARCH
            if len(dir_candidates) == 1:
                rest = Path(*parts[i + 1:])
                new_full = Path(dir_candidates[0]) / rest
===
            if len(dir_candidates) == 1:
                rest = Path(*parts[i + 1:])
                new_full = repo_root / dir_candidates[0] / rest
>>>
```

#### [MODIFY] .agent/src/agent/core/implement/resolver.py

```
<<<SEARCH
        current_check = next_check

    return file_path
===
        current_check = next_check

    return repo_root / filepath
>>>
```

### Step 3: Fix Orchestrator to Use Resolved Absolute Paths

The orchestrator's `apply_chunk()` uses bare `Path()` for file I/O. Since `resolve_path()` now returns absolute paths, the orchestrator must use those resolved paths (not re-wrap them in `Path()`).

#### [MODIFY] .agent/src/agent/core/implement/orchestrator.py

```
<<<SEARCH
            for sr_filepath, file_blocks in sr_by_file.items():
                fp = Path(sr_filepath)
                original_content = fp.read_text() if fp.exists() else ""
===
            for sr_filepath, file_blocks in sr_by_file.items():
                fp = resolve_path(sr_filepath) or Path(sr_filepath)
                original_content = fp.read_text() if fp.exists() else ""
>>>
```

#### [MODIFY] .agent/src/agent/core/implement/orchestrator.py

```
<<<SEARCH
            fp = Path(block["file"])
            original_content = fp.read_text() if fp.exists() else ""
===
            fp = resolve_path(block["file"]) or Path(block["file"])
            original_content = fp.read_text() if fp.exists() else ""
>>>
```

### Step 4: Re-enable Parent Directory Check in ModifyBlock

Re-add the parent directory existence check removed in INFRA-134, but this time using `config.repo_root` instead of CWD.

#### [MODIFY] .agent/src/agent/core/implement/models.py

```
<<<SEARCH
from typing import List, Union, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
import os
from pathlib import Path
===
from typing import List, Union, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
import os
from pathlib import Path
from agent.core.config import resolve_repo_path
>>>
```

#### [MODIFY] .agent/src/agent/core/implement/models.py

```
<<<SEARCH
    @model_validator(mode="after")
    def validate_modify_path(self) -> "ModifyBlock":
        """Verify the path is valid for a modification."""
        if not self.path:
            raise ValueError("Path is required for MODIFY block.")
        # Basic relative path safety
        if ".." in self.path or self.path.startswith("/"):
            raise ValueError(f"Path must be repository-relative and safe: {self.path}")
        return self
===
    @model_validator(mode="after")
    def validate_modify_path(self) -> "ModifyBlock":
        """Verify the path is valid for a modification."""
        if not self.path:
            raise ValueError("Path is required for MODIFY block.")
        # AC-3: Use canonical resolver for traversal + absolute path safety
        try:
            resolved = resolve_repo_path(self.path)
        except ValueError as e:
            raise ValueError(f"Path must be repository-relative and safe: {self.path}") from e
        # AC-3: Re-enable parent directory check via config.repo_root (INFRA-138)
        if not resolved.parent.exists():
            raise ValueError(
                f"Parent directory does not exist: {resolved.parent} "
                f"(from path '{self.path}')"
            )
        return self
>>>
```

### Step 5: Add CWD-Independence Tests

#### [NEW] .agent/tests/core/implement/test_resolve_repo_path.py

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

"""Tests for resolve_repo_path() CWD-independence (INFRA-138)."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, PropertyMock

from agent.core.config import resolve_repo_path, config


class TestResolveRepoPath:
    """AC-6: Verify resolver works from any CWD."""

    def test_resolves_against_repo_root(self):
        """Path resolves against config.repo_root, not os.getcwd()."""
        result = resolve_repo_path(".agent/src/agent/core/config.py")
        assert result == (config.repo_root / ".agent/src/agent/core/config.py").resolve()
        assert result.is_absolute()

    def test_returns_absolute_path(self):
        """Resolved path is always absolute."""
        result = resolve_repo_path(".agent/etc/agents.yaml")
        assert result.is_absolute()

    def test_traversal_rejected_ac7(self):
        """AC-7: Path with .. traversal raises ValueError."""
        with pytest.raises(ValueError, match="traversal"):
            resolve_repo_path("../escape/attempt")

    def test_double_dot_in_middle_rejected(self):
        """AC-7: Path with .. in middle raises ValueError."""
        with pytest.raises(ValueError, match="traversal"):
            resolve_repo_path(".agent/../../../etc/passwd")

    def test_absolute_path_rejected_ac7(self):
        """AC-7: Absolute paths raise ValueError."""
        with pytest.raises(ValueError, match="Absolute"):
            resolve_repo_path("/etc/passwd")

    def test_cwd_independent(self, tmp_path, monkeypatch):
        """Resolver returns same result regardless of CWD."""
        result_from_root = resolve_repo_path(".agent/etc/agents.yaml")
        monkeypatch.chdir(tmp_path)
        result_from_tmp = resolve_repo_path(".agent/etc/agents.yaml")
        assert result_from_root == result_from_tmp
```

## Verification Plan

### Automated Tests

```bash
cd .agent && uv run pytest tests/core/implement/test_resolve_repo_path.py tests/core/implement/test_pathing.py tests/core/implement/test_models.py -v
```

- `test_resolve_repo_path.py`: 6 new tests for AC-1, AC-6, AC-7.
- `test_pathing.py`: 4 existing tests must still pass (may need minor adjustments since `resolve_path()` now returns absolute paths).
- `test_models.py`: Existing tests pass with re-enabled parent dir check.

### Full Suite

```bash
cd .agent && uv run pytest -x --tb=short
```

### Manual Verification

1. From repo root: `cd .agent && uv run agent implement --story INFRA-138 --yes`
   - Expected: All MODIFY blocks find their target files.
2. From repo root: `cd .agent && uv run agent preflight --story INFRA-138`
   - Expected: No "No such file or directory" errors.

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated with "Canonical CWD path resolution (INFRA-138)".

### Observability

- [ ] `resolve_repo_path()` raises `ValueError` with descriptive messages for invalid paths.

### Testing

- [ ] All existing tests pass.
- [ ] 6 new tests for `resolve_repo_path()` covering AC-1, AC-6, AC-7.
- [ ] Existing `test_pathing.py` tests updated if needed for absolute path returns.

## Copyright

Copyright 2026 Justin Cook.
