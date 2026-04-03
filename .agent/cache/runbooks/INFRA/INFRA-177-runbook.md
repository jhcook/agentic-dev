# Runbook: Implementation Runbook for INFRA-177

## State

ACCEPTED

## Implementation Steps

### Step 1: Architecture & Design Review

Gate 0 is a projected LOC check inserted as the first gate in `run_generation_gates()`. It prevents runbooks that would push any tracked file above `config.max_file_loc` (default 500 lines) from proceeding past the generation loop.

**Delta formula for `[MODIFY]`:**
`projected_loc = current_loc + (replace_lines - search_lines)` where line counts use `.strip("\n").count("\n") + 1` (strips trailing AI-hallucinated blank lines).

**Scope:** `[MODIFY]` blocks where the target file exists on disk. `[NEW]` blocks: full content line count. Missing `[MODIFY]` targets are no-ops (delegated to the S/R gate).

**Injection point:** Before Gate 1 (schema) in `run_generation_gates()`, operating on the already-parsed `blocks = parse_code_blocks(content)` which is called later — so Gate 0 parses its own block list from content.

**CHANGELOG entry:**

#### [MODIFY] CHANGELOG.md

```markdown
<<<SEARCH
## [Unreleased]

**Added**
===
## [Unreleased]

**Added**
- INFRA-177: Gate 0 projected LOC check at runbook generation time — prevents files exceeding `config.max_file_loc` from being generated.
>>>
```

### Step 2: Core Logic — Create `loc_guard.py`

`check_projected_loc` is extracted into its own module (`agent/core/implement/loc_guard.py`) so that `guards.py` stays under the 1000-line hard limit. It is re-exported from `guards.py` for backward compatibility. A `CodeBlock` TypedDict enforces the structure of the parsed blocks dict.

#### [NEW] .agent/src/agent/core/implement/loc_guard.py

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

"""Gate 0: Projected LOC check for the runbook generation pipeline (INFRA-177)."""

import logging
from pathlib import Path
from typing import List

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict

from agent.core.config import config

logger = logging.getLogger(__name__)


class CodeBlock(TypedDict, total=False):
    path: str
    operation: str
    content: str
    search: str
    replace: str


def check_projected_loc(blocks: List[CodeBlock], project_root: Path) -> List[str]:
    """Gate 0: Returns correction strings for blocks that would exceed config.max_file_loc."""
    limit = getattr(config, "max_file_loc", 500)
    errors: List[str] = []
    for block in blocks:
        file_path = block.get("path", "")
        operation = block.get("operation", "")
        if not file_path or operation not in ("NEW", "MODIFY"):
            continue
        full_path = (project_root / file_path).resolve()
        if operation == "NEW":
            stripped = block.get("content", "").strip("\n")
            projected_loc = stripped.count("\n") + 1 if stripped else 0
            current_loc = 0
        else:
            if not full_path.exists():
                continue
            raw = full_path.read_text(encoding="utf-8")
            current_loc = raw.count("\n") + (0 if raw.endswith("\n") else 1)
            s = block.get("search", "").strip("\n")
            r = block.get("replace", "").strip("\n")
            projected_loc = max(0, current_loc + (r.count("\n") + 1 if r else 0) - (s.count("\n") + 1 if s else 0))
        if projected_loc > limit:
            logger.warning("projected_loc_gate_fail", extra={"file": file_path, "current_loc": current_loc, "projected_loc": projected_loc, "limit": limit})
            errors.append(f"File '{file_path}' would reach {projected_loc} lines after this change (limit: {limit}). Split the change into smaller modules.")
    return errors
```

### Step 3: Re-export from `guards.py`

`check_projected_loc` is removed from `guards.py` and re-exported from `loc_guard` to keep backward compat with any caller that imports from `guards`.

#### [MODIFY] .agent/src/agent/core/implement/guards.py

```python
<<<SEARCH
logger = logging.getLogger(__name__)

meter = metrics.get_meter("agent.guardrails")
===
logger = logging.getLogger(__name__)

# INFRA-177: check_projected_loc lives in loc_guard.py (guards.py LOC budget).
from agent.core.implement.loc_guard import check_projected_loc  # noqa: E402,F401

meter = metrics.get_meter("agent.guardrails")
>>>
```


#### [MODIFY] .agent/src/agent/core/implement/guards.py

```python
<<<SEARCH
logger = logging.getLogger(__name__)
===
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# INFRA-177: Gate 0 — Projected LOC check
# ---------------------------------------------------------------------------

def check_projected_loc(blocks: List[Dict[str, Any]], project_root: Path) -> List[str]:
    """Gate 0: Reject blocks that would push any file past config.max_file_loc.

    Runs before schema validation so the AI gets early feedback on size
    before any expensive S/R matching or code gate processing.

    Args:
        blocks: Parsed code blocks from the runbook (dicts with 'path',
            'operation', 'content', 'search', 'replace' keys).
        project_root: Repository root used to resolve relative file paths.

    Returns:
        List of human-readable correction strings, one per violation.
        Empty list means all blocks are within the LOC limit.
    """
    limit = getattr(config, "max_file_loc", 500)
    errors: List[str] = []

    for block in blocks:
        file_path = block.get("path", "")
        operation = block.get("operation", "")

        if not file_path or operation not in ("NEW", "MODIFY"):
            continue

        full_path = (project_root / file_path).resolve()

        if operation == "NEW":
            content = block.get("content", "")
            stripped = content.strip("\n")
            projected_loc = stripped.count("\n") + 1 if stripped else 0
            current_loc = 0
        else:  # MODIFY
            if not full_path.exists():
                continue  # AC-4: no-op for missing files
            try:
                raw = full_path.read_text(encoding="utf-8")
            except OSError as exc:
                logger.warning("projected_loc_read_fail", extra={"file": file_path, "error": str(exc)})
                continue
            current_loc = raw.count("\n") + (0 if raw.endswith("\n") else 1)

            search_text = block.get("search", "")
            replace_text = block.get("replace", "")
            search_lines = search_text.strip("\n").count("\n") + 1 if search_text.strip("\n") else 0
            replace_lines = replace_text.strip("\n").count("\n") + 1 if replace_text.strip("\n") else 0
            projected_loc = max(0, current_loc + replace_lines - search_lines)

        if projected_loc > limit:
            logger.warning(
                "projected_loc_gate_fail",
                extra={
                    "file": file_path,
                    "current_loc": current_loc,
                    "projected_loc": projected_loc,
                    "limit": limit,
                },
            )
            errors.append(
                f"File '{file_path}' would reach {projected_loc} lines after this change "
                f"(limit: {limit}). Split the change into smaller modules or use a more "
                f"targeted modification to stay within the architectural LOC boundary."
            )

    return errors
>>>
```

### Step 4: Wire Gate 0 and Gate 1b into `run_generation_gates`

Three targeted changes to `runbook_gates.py`:
1. Add `check_projected_loc` and `detect_malformed_modify_blocks` to imports.
2. Hoist `parse_code_blocks(content)` to a single call before Gate 0 (shared with Gate 2).
3. Add the Gate 0 (LOC) block and Gate 1b (malformed MODIFY) block.

#### [MODIFY] .agent/src/agent/commands/runbook_gates.py

```python
<<<SEARCH
from agent.core.implement.guards import (
    validate_code_block,
    check_impact_analysis_completeness,
    check_adr_refs,
    check_stub_implementations,
)
from agent.core.implement.orchestrator import validate_runbook_schema
from agent.core.implement.parser import parse_code_blocks
===
from agent.core.implement.guards import (
    check_projected_loc,
    validate_code_block,
    check_impact_analysis_completeness,
    check_adr_refs,
    check_stub_implementations,
)
from agent.core.implement.orchestrator import validate_runbook_schema
from agent.core.implement.parser import detect_malformed_modify_blocks, parse_code_blocks
>>>
<<<SEARCH
    # 1. Schema validation
===
    # Parse code blocks once — shared by Gate 0 (LOC) and Gate 2 (code gates)
    parsed_blocks = parse_code_blocks(content)

    # 0. Projected LOC gate (INFRA-177)
    with tracer.start_as_current_span("projected_loc_gate") as loc_span:
        loc_errors = check_projected_loc(parsed_blocks, config.repo_root)
        loc_span.set_attribute("validation.passed", not bool(loc_errors))
        loc_span.set_attribute("validation.error_count", len(loc_errors))

    if loc_errors:
        logger.warning("projected_loc_gate_fail", extra={"story_id": story_id, "errors": loc_errors})
        correction_parts.append("LOC GATE VIOLATIONS (Gate 0):\n" + "\n".join(f"- {e}" for e in loc_errors))

    # 1. Schema validation
>>>
<<<SEARCH
    if schema_violations:
        logger.warning("runbook_schema_fail", extra={"attempt": attempt, "story_id": story_id})
        correction_parts.append(
            format_runbook_errors(schema_violations) + "\nPlease fix these schema errors."
        )

    # 2. Code Gate Self-Healing (INFRA-155 AC-1)
===
    if schema_violations:
        logger.warning("runbook_schema_fail", extra={"attempt": attempt, "story_id": story_id})
        correction_parts.append(format_runbook_errors(schema_violations) + "\nPlease fix these schema errors.")

    # 1b. Malformed [MODIFY] block detection (AC-6 — INFRA-177)
    with tracer.start_as_current_span("malformed_modify_gate") as mal_span:
        malformed_paths = detect_malformed_modify_blocks(content)
        mal_span.set_attribute("validation.passed", not bool(malformed_paths))
        mal_span.set_attribute("validation.malformed_count", len(malformed_paths))

    if malformed_paths:
        logger.warning("malformed_modify_block_gate", extra={"story_id": story_id, "files": malformed_paths})
        detail = "\n".join(f"  - {p}" for p in malformed_paths)
        correction_parts.append(
            f"MALFORMED [MODIFY] BLOCKS (Gate 1b):\n{detail}\n"
            "Each listed [MODIFY] block has a fenced code block but is missing "
            "<<<SEARCH/===/>>> markers. Replace it with a proper S/R diff."
        )

    # 2. Code Gate Self-Healing (INFRA-155 AC-1)
>>>
```


### Step 5: Test Suite

#### [NEW] .agent/tests/commands/test_infra_177_projected_loc.py

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

"""Unit tests for INFRA-177: Gate 0 projected LOC check."""

from pathlib import Path
from unittest.mock import patch

import pytest

from agent.core.implement.guards import check_projected_loc


# ---------------------------------------------------------------------------
# AC-1: MODIFY block that would push file over limit → correction
# ---------------------------------------------------------------------------

def test_modify_exceeds_limit(tmp_path: Path) -> None:
    """MODIFY adds 20 lines to a 490-line file — projects to 510, blocked."""
    target = tmp_path / "oversized.py"
    target.write_text("line\n" * 490)

    blocks = [
        {
            "path": "oversized.py",
            "operation": "MODIFY",
            "search": "line",          # 1 line
            "replace": "line\n" * 21,  # 21 lines → delta +20
        }
    ]
    with patch("agent.core.implement.guards.config") as mock_cfg:
        mock_cfg.max_file_loc = 500
        errors = check_projected_loc(blocks, tmp_path)

    assert len(errors) == 1
    assert "would reach 510 lines" in errors[0]
    assert "oversized.py" in errors[0]


# ---------------------------------------------------------------------------
# AC-2: NEW block whose content exceeds limit → correction
# ---------------------------------------------------------------------------

def test_new_block_exceeds_limit(tmp_path: Path) -> None:
    """NEW block with 520-line content is blocked."""
    blocks = [
        {
            "path": "brand_new.py",
            "operation": "NEW",
            "content": "line\n" * 519 + "line",  # 520 lines
        }
    ]
    with patch("agent.core.implement.guards.config") as mock_cfg:
        mock_cfg.max_file_loc = 500
        errors = check_projected_loc(blocks, tmp_path)

    assert len(errors) == 1
    assert "would reach 520 lines" in errors[0]


# ---------------------------------------------------------------------------
# AC-3: Blocks within limit → clean pass
# ---------------------------------------------------------------------------

def test_modify_within_limit(tmp_path: Path) -> None:
    """MODIFY that adds 10 lines to a 470-line file passes cleanly."""
    target = tmp_path / "ok.py"
    target.write_text("line\n" * 470)

    blocks = [
        {
            "path": "ok.py",
            "operation": "MODIFY",
            "search": "line",
            "replace": "line\n" * 11,  # delta +10, projected 480
        }
    ]
    with patch("agent.core.implement.guards.config") as mock_cfg:
        mock_cfg.max_file_loc = 500
        assert check_projected_loc(blocks, tmp_path) == []


def test_new_block_within_limit(tmp_path: Path) -> None:
    """NEW block with 50 lines passes cleanly."""
    blocks = [
        {
            "path": "fresh.py",
            "operation": "NEW",
            "content": "line\n" * 50,
        }
    ]
    with patch("agent.core.implement.guards.config") as mock_cfg:
        mock_cfg.max_file_loc = 500
        assert check_projected_loc(blocks, tmp_path) == []


# ---------------------------------------------------------------------------
# AC-4: Missing MODIFY target → no-op
# ---------------------------------------------------------------------------

def test_modify_missing_file_is_noop(tmp_path: Path) -> None:
    """MODIFY on a non-existent file is silently skipped (delegated to S/R gate)."""
    blocks = [
        {
            "path": "does_not_exist.py",
            "operation": "MODIFY",
            "search": "old",
            "replace": "new",
        }
    ]
    with patch("agent.core.implement.guards.config") as mock_cfg:
        mock_cfg.max_file_loc = 500
        assert check_projected_loc(blocks, tmp_path) == []


# ---------------------------------------------------------------------------
# Negative delta (shrinking file) stays within limit → pass
# ---------------------------------------------------------------------------

def test_modify_negative_delta_passes(tmp_path: Path) -> None:
    """Shrinking a 550-line file by 90 lines projects to 460 — passes."""
    target = tmp_path / "shrinking.py"
    target.write_text("line\n" * 550)

    blocks = [
        {
            "path": "shrinking.py",
            "operation": "MODIFY",
            "search": "line\n" * 100,
            "replace": "line\n" * 10,  # delta -90, projected 460
        }
    ]
    with patch("agent.core.implement.guards.config") as mock_cfg:
        mock_cfg.max_file_loc = 500
        assert check_projected_loc(blocks, tmp_path) == []
```

### Step 6: Deployment & Rollback

**Deployment**
1. `agent implement --apply INFRA-177`
2. `agent preflight --story INFRA-177`
3. Smoke: run `agent new-runbook` on any story; confirm `projected_loc_gate_fail` events appear when a block would exceed 500 LOC.

**Rollback**
Gate 0 is a pure function call. To disable, comment out the `check_projected_loc` block in `run_generation_gates`. No state mutations, no migrations.

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
