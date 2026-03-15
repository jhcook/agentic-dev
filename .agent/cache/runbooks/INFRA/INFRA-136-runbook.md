# STORY-ID: INFRA-136: Execution Tracing and Scope Guardrails with Langfuse

## State

ACCEPTED

## Goal Description

Add scope-bounding and Langfuse tracing to the implement orchestrator. Any file touched by `apply_chunk()` that is not declared in the runbook's `[MODIFY]`, `[NEW]`, or `[DELETE]` headers is blocked with a `scope_violation` structured log. Langfuse trace spans wrap each `apply_chunk()` call, and a hallucination rate score is computed at the end of each run.

## Linked Journeys

- JRN-065

## Panel Review Findings

### @Architect
- **Scope**: 4 files modified, 1 new test file. ~175 net new lines — well within budget.
- **Pattern**: `extract_approved_files()` follows the same regex pattern as `extract_modify_files()`. The scope guard is a simple set membership check in `apply_chunk()`.

### @Security
- **No sensitive data in traces**: Only file paths and step indices are set as span attributes — no file content.
- **Scope guard**: Prevents unintentional modification of files outside the runbook scope, reducing blast radius.

### @QA
- **Regression risk**: Low. Scope guard defaults to warn + skip for unapproved files, so existing runbooks without `cross_cutting` annotations will surface warnings but won't be silently broken.
- **Test coverage**: 6 new tests covering extractors, scope guard allow/block, cross_cutting bypass, and hallucination rate scoring.

### @Observability
- **Langfuse spans**: Each `apply_chunk()` call emits `implement.apply_chunk` span with `story_id`, `step_index`, `file_path` attributes.
- **Hallucination rate**: `scope_violations / total_blocks` ratio set as span attribute at run end.

## Codebase Introspection

### Targeted File Contents

#### .agent/src/agent/core/implement/parser.py (312 LOC)
- `extract_modify_files()` (line 114): Only captures `[MODIFY]` markers. Need broader `extract_approved_files()` that also captures `[NEW]` and `[DELETE]`.

#### .agent/src/agent/core/implement/orchestrator.py (244 LOC)
- `Orchestrator.__init__()` (line 106): Accepts `story_id`, `yes`, `legacy_apply`. Need `approved_files: Optional[Set[str]]` and `cross_cutting_files: Optional[Set[str]]`.
- `apply_chunk()` (line 120): Processes search/replace + full-file blocks. Insert scope guard before each file operation.
- `_tracer` (line 42): Already available at module level via `from opentelemetry import trace`.

#### .agent/src/agent/commands/implement.py (938 LOC)
- Line 666: `orchestrator = Orchestrator(story_id, yes=yes, legacy_apply=legacy_apply)` — wire `approved_files`.
- Line 785: `orchestrator_fc = Orchestrator(story_id, yes=yes, legacy_apply=legacy_apply)` — wire `approved_files`.
- Line 68-74: Import block — add `extract_approved_files` and `extract_cross_cutting_files`.

## Implementation Steps

### Step 1: Add `extract_approved_files()` and `extract_cross_cutting_files()` to Parser

#### [MODIFY] .agent/src/agent/core/implement/parser.py

```
<<<SEARCH
def extract_modify_files(runbook_content: str) -> List[str]:
    """Scan a runbook for [MODIFY] markers and return referenced file paths.

    Args:
        runbook_content: Raw runbook markdown.

    Returns:
        Deduplicated list of file path strings in order of first appearance.
    """
    seen: set = set()
    result: List[str] = []
    for path in re.findall(r'\[MODIFY\]\s*`?([^\n`]+)`?', runbook_content, re.IGNORECASE):
        path = path.strip()
        if path not in seen:
            seen.add(path)
            result.append(path)
    return result
===
def extract_modify_files(runbook_content: str) -> List[str]:
    """Scan a runbook for [MODIFY] markers and return referenced file paths.

    Args:
        runbook_content: Raw runbook markdown.

    Returns:
        Deduplicated list of file path strings in order of first appearance.
    """
    seen: set = set()
    result: List[str] = []
    for path in re.findall(r'\[MODIFY\]\s*`?([^\n`]+)`?', runbook_content, re.IGNORECASE):
        path = path.strip()
        if path not in seen:
            seen.add(path)
            result.append(path)
    return result


def extract_approved_files(runbook_content: str) -> set:
    """Extract all declared file paths from [MODIFY], [NEW], and [DELETE] headers.

    This is the approved file set for scope-bounding (INFRA-136 AC-2).

    Args:
        runbook_content: Raw runbook markdown.

    Returns:
        Set of file path strings declared in the runbook.
    """
    paths: set = set()
    for match in re.findall(
        r'\[(?:MODIFY|NEW|DELETE)\]\s*`?([^\n`]+)`?',
        runbook_content, re.IGNORECASE,
    ):
        paths.add(match.strip())
    return paths


def extract_cross_cutting_files(runbook_content: str) -> set:
    """Extract file paths annotated with cross_cutting: true (INFRA-136 AC-4).

    Recognises ``<!-- cross_cutting: true -->`` on the line before or after
    a ``[MODIFY]``/``[NEW]`` header.

    Args:
        runbook_content: Raw runbook markdown.

    Returns:
        Set of file path strings with cross_cutting relaxation.
    """
    paths: set = set()
    for match in re.findall(
        r'<!--\s*cross_cutting:\s*true\s*-->\s*\n'
        r'####\s*\[(?:MODIFY|NEW)\]\s*`?([^\n`]+)`?',
        runbook_content, re.IGNORECASE,
    ):
        paths.add(match.strip())
    for match in re.findall(
        r'####\s*\[(?:MODIFY|NEW)\]\s*`?([^\n`]+)`?\s*\n'
        r'\s*<!--\s*cross_cutting:\s*true\s*-->',
        runbook_content, re.IGNORECASE,
    ):
        paths.add(match.strip())
    return paths
>>>
```

### Step 2: Add Scope Guard and Trace Spans to Orchestrator

#### [MODIFY] .agent/src/agent/core/implement/orchestrator.py

```
<<<SEARCH
from typing import Dict, List, Optional, Tuple
from .parser import (
    parse_code_blocks,
    parse_search_replace_blocks,
    extract_modify_files,
    detect_malformed_modify_blocks,
    validate_runbook_schema,
    split_runbook_into_chunks,
)
===
from typing import Dict, List, Optional, Set, Tuple
from .parser import (
    parse_code_blocks,
    parse_search_replace_blocks,
    extract_modify_files,
    extract_approved_files,
    extract_cross_cutting_files,
    detect_malformed_modify_blocks,
    validate_runbook_schema,
    split_runbook_into_chunks,
)
>>>
```

#### [MODIFY] .agent/src/agent/core/implement/orchestrator.py

```
<<<SEARCH
    def __init__(self, story_id: str, yes: bool = False, legacy_apply: bool = False) -> None:
        """Initialise the Orchestrator.

        Args:
            story_id: Story ID used in commit messages and log fields.
            yes: Skip all confirmation prompts.
            legacy_apply: Bypass safe-apply size guard.
        """
        self.story_id = story_id
        self.yes = yes
        self.legacy_apply = legacy_apply
        self.rejected_files: List[str] = []
        self.run_modified_files: List[str] = []
===
    def __init__(
        self,
        story_id: str,
        yes: bool = False,
        legacy_apply: bool = False,
        approved_files: Optional[Set[str]] = None,
        cross_cutting_files: Optional[Set[str]] = None,
    ) -> None:
        """Initialise the Orchestrator.

        Args:
            story_id: Story ID used in commit messages and log fields.
            yes: Skip all confirmation prompts.
            legacy_apply: Bypass safe-apply size guard.
            approved_files: Set of file paths declared in the runbook (AC-2).
            cross_cutting_files: Files with cross_cutting relaxation (AC-4).
        """
        self.story_id = story_id
        self.yes = yes
        self.legacy_apply = legacy_apply
        self.approved_files = approved_files
        self.cross_cutting_files = cross_cutting_files or set()
        self.rejected_files: List[str] = []
        self.run_modified_files: List[str] = []
        self.total_blocks: int = 0
        self.scope_violations: int = 0
>>>
```

#### [MODIFY] .agent/src/agent/core/implement/orchestrator.py

```
<<<SEARCH
        sr_blocks = parse_search_replace_blocks(chunk_result)
        sr_handled: set = set()
        if sr_blocks:
            sr_by_file: Dict[str, List[Dict[str, str]]] = defaultdict(list)
            for block in sr_blocks:
                sr_by_file[block["file"]].append(block)
            for sr_filepath, file_blocks in sr_by_file.items():
                fp = resolve_path(sr_filepath) or Path(sr_filepath)
===
        sr_blocks = parse_search_replace_blocks(chunk_result)
        sr_handled: set = set()
        if sr_blocks:
            sr_by_file: Dict[str, List[Dict[str, str]]] = defaultdict(list)
            for block in sr_blocks:
                sr_by_file[block["file"]].append(block)
            for sr_filepath, file_blocks in sr_by_file.items():
                self.total_blocks += 1
                if not self._check_scope(sr_filepath, step_index):
                    continue
                fp = resolve_path(sr_filepath) or Path(sr_filepath)
>>>
```

#### [MODIFY] .agent/src/agent/core/implement/orchestrator.py

```
<<<SEARCH
        code_blocks = [b for b in parse_code_blocks(chunk_result) if b["file"] not in sr_handled]
        for block in code_blocks:
            violations = enforce_docstrings(block["file"], block["content"])
===
        code_blocks = [b for b in parse_code_blocks(chunk_result) if b["file"] not in sr_handled]
        for block in code_blocks:
            self.total_blocks += 1
            if not self._check_scope(block["file"], step_index):
                continue
            violations = enforce_docstrings(block["file"], block["content"])
>>>
```

#### [MODIFY] .agent/src/agent/core/implement/orchestrator.py

```
<<<SEARCH
    def print_incomplete_summary(self) -> None:
===
    def _check_scope(self, filepath: str, step_index: int) -> bool:
        """Check if a file is within the approved scope (AC-2, AC-4, AC-5).

        Args:
            filepath: Repo-relative file path being modified.
            step_index: 1-based step number for logging.

        Returns:
            True if the file is approved, False if scope-violated.
        """
        if self.approved_files is None:
            return True  # No approved set → no scope enforcement
        if filepath in self.approved_files or filepath in self.cross_cutting_files:
            return True
        self.scope_violations += 1
        self.rejected_files.append(filepath)
        _console.print(
            f"[bold red]🚫 SCOPE VIOLATION: '{filepath}' is not declared in the "
            f"runbook (step {step_index}). Skipping.[/bold red]"
        )
        logging.warning(
            "scope_violation file=%s step=%d story=%s approved_files=%r",
            filepath, step_index, self.story_id,
            sorted(self.approved_files) if self.approved_files else [],
        )
        return False

    def get_hallucination_rate(self) -> float:
        """Compute the hallucination rate (AC-3).

        Returns:
            Ratio of scope violations to total blocks, or 0.0 if no blocks.
        """
        if self.total_blocks == 0:
            return 0.0
        return self.scope_violations / self.total_blocks

    def print_incomplete_summary(self) -> None:
>>>
```

### Step 3: Wrap `apply_chunk()` in a Trace Span

#### [MODIFY] .agent/src/agent/core/implement/orchestrator.py

```
<<<SEARCH
    def apply_chunk(self, chunk_result: str, step_index: int) -> Tuple[int, List[str]]:
        """Apply all blocks in a single AI-generated chunk.

        Processes search/replace blocks first, then full-file blocks.
        For each full-file block runs the docstring gate (AC-10) before
        writing. Fixes the block_loc uninitialised-variable bug (AC-9) by
        resetting ``block_loc`` to ``0`` before each apply call.

        Args:
            chunk_result: Raw AI output for this step.
            step_index: 1-based step number (for logging).

        Returns:
            Tuple of ``(step_loc, step_modified_files)``.
        """
        from agent.core.implement.guards import (
===
    def apply_chunk(self, chunk_result: str, step_index: int) -> Tuple[int, List[str]]:
        """Apply all blocks in a single AI-generated chunk.

        Processes search/replace blocks first, then full-file blocks.
        For each full-file block runs the docstring gate (AC-10) before
        writing. Fixes the block_loc uninitialised-variable bug (AC-9) by
        resetting ``block_loc`` to ``0`` before each apply call.

        Wraps execution in a Langfuse/OTLP trace span (INFRA-136 AC-1).

        Args:
            chunk_result: Raw AI output for this step.
            step_index: 1-based step number (for logging).

        Returns:
            Tuple of ``(step_loc, step_modified_files)``.
        """
        span = None
        if _tracer:
            span = _tracer.start_span("implement.apply_chunk")
            span.set_attribute("story_id", self.story_id)
            span.set_attribute("step_index", step_index)

        from agent.core.implement.guards import (
>>>
```

#### [MODIFY] .agent/src/agent/core/implement/orchestrator.py

```
<<<SEARCH
        self.run_modified_files.extend(step_modified_files)
        return step_loc, step_modified_files
===
        self.run_modified_files.extend(step_modified_files)

        if span:
            span.set_attribute("files_modified", len(step_modified_files))
            span.set_attribute("scope_violations", self.scope_violations)
            span.set_attribute("hallucination_rate", self.get_hallucination_rate())
            span.end()

        return step_loc, step_modified_files
>>>
```

### Step 4: Wire Approved Files from Implement Command

#### [MODIFY] .agent/src/agent/commands/implement.py

```
<<<SEARCH
from agent.core.implement.parser import (  # noqa: F401
    detect_malformed_modify_blocks,
    extract_modify_files,
    parse_code_blocks,
    parse_search_replace_blocks,
    split_runbook_into_chunks,
    validate_runbook_schema,
)
===
from agent.core.implement.parser import (  # noqa: F401
    detect_malformed_modify_blocks,
    extract_approved_files,
    extract_cross_cutting_files,
    extract_modify_files,
    parse_code_blocks,
    parse_search_replace_blocks,
    split_runbook_into_chunks,
    validate_runbook_schema,
)
>>>
```

#### [MODIFY] .agent/src/agent/commands/implement.py

```
<<<SEARCH
            completed_steps = 0
            orchestrator = Orchestrator(story_id, yes=yes, legacy_apply=legacy_apply)
===
            completed_steps = 0
            _approved = extract_approved_files(runbook_content)
            _cross_cutting = extract_cross_cutting_files(runbook_content)
            orchestrator = Orchestrator(
                story_id, yes=yes, legacy_apply=legacy_apply,
                approved_files=_approved, cross_cutting_files=_cross_cutting,
            )
>>>
```

#### [MODIFY] .agent/src/agent/commands/implement.py

```
<<<SEARCH
            orchestrator_fc = Orchestrator(story_id, yes=yes, legacy_apply=legacy_apply)
===
            orchestrator_fc = Orchestrator(
                story_id, yes=yes, legacy_apply=legacy_apply,
                approved_files=_approved, cross_cutting_files=_cross_cutting,
            )
>>>
```

### Step 5: Add Scope Guard Tests

#### [NEW] .agent/tests/core/implement/test_scope_guard.py

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

"""Tests for INFRA-136 scope guardrails and approved file extraction."""

import pytest

from agent.core.implement.parser import (
    extract_approved_files,
    extract_cross_cutting_files,
)
from agent.core.implement.orchestrator import Orchestrator


SAMPLE_RUNBOOK = (
    "## Implementation Steps\n\n"
    "### Step 1: Modify config\n\n"
    "#### [MODIFY] .agent/src/agent/core/config.py\n\n"
    "```\n<<<SEARCH\nold\n===\nnew\n>>>\n```\n\n"
    "### Step 2: Create helper\n\n"
    "#### [NEW] .agent/src/agent/core/helper.py\n\n"
    "```python\n\"\"\"Helper.\"\"\"\ndef helper():\n    \"\"\"Help.\"\"\"\n    pass\n```\n\n"
    "### Step 3: Remove legacy\n\n"
    "#### [DELETE] .agent/src/agent/core/old.py\n\n"
    "<!-- Replaced by helper.py -->\n"
)

CROSS_CUTTING_RUNBOOK = (
    "## Implementation Steps\n\n"
    "### Step 1: Update shared util\n\n"
    "<!-- cross_cutting: true -->\n"
    "#### [MODIFY] .agent/src/agent/core/utils.py\n\n"
    "```\n<<<SEARCH\nold\n===\nnew\n>>>\n```\n"
)


class TestExtractApprovedFiles:
    """Tests for extract_approved_files() — AC-2."""

    def test_extracts_all_block_types(self):
        """Captures MODIFY, NEW, and DELETE paths."""
        approved = extract_approved_files(SAMPLE_RUNBOOK)
        assert ".agent/src/agent/core/config.py" in approved
        assert ".agent/src/agent/core/helper.py" in approved
        assert ".agent/src/agent/core/old.py" in approved
        assert len(approved) == 3

    def test_empty_runbook(self):
        """Empty content returns empty set."""
        assert extract_approved_files("") == set()


class TestExtractCrossCuttingFiles:
    """Tests for extract_cross_cutting_files() — AC-4."""

    def test_extracts_annotated_file(self):
        """Captures file with cross_cutting annotation before header."""
        cc = extract_cross_cutting_files(CROSS_CUTTING_RUNBOOK)
        assert ".agent/src/agent/core/utils.py" in cc

    def test_not_cross_cutting_without_annotation(self):
        """Files without annotation are not cross_cutting."""
        cc = extract_cross_cutting_files(SAMPLE_RUNBOOK)
        assert len(cc) == 0


class TestScopeGuard:
    """Tests for Orchestrator._check_scope() — AC-2, AC-5."""

    def test_approved_file_allowed(self):
        """File in approved set passes scope check."""
        orch = Orchestrator(
            "TEST-001", approved_files={".agent/src/agent/core/config.py"},
        )
        assert orch._check_scope(".agent/src/agent/core/config.py", 1) is True
        assert orch.scope_violations == 0

    def test_unapproved_file_blocked(self):
        """File not in approved set is scope-violated."""
        orch = Orchestrator(
            "TEST-001", approved_files={".agent/src/agent/core/config.py"},
        )
        result = orch._check_scope(".agent/src/agent/core/rogue.py", 1)
        assert result is False
        assert orch.scope_violations == 1
        assert ".agent/src/agent/core/rogue.py" in orch.rejected_files

    def test_cross_cutting_bypasses_scope(self):
        """File in cross_cutting set bypasses scope check."""
        orch = Orchestrator(
            "TEST-001",
            approved_files={".agent/src/agent/core/config.py"},
            cross_cutting_files={".agent/src/agent/core/utils.py"},
        )
        assert orch._check_scope(".agent/src/agent/core/utils.py", 1) is True
        assert orch.scope_violations == 0

    def test_no_approved_set_allows_all(self):
        """When approved_files is None, scope is not enforced."""
        orch = Orchestrator("TEST-001")
        assert orch._check_scope("any/file.py", 1) is True


class TestHallucinationRate:
    """Tests for hallucination rate scoring — AC-3."""

    def test_zero_blocks_returns_zero(self):
        """No blocks → 0.0 rate."""
        orch = Orchestrator("TEST-001")
        assert orch.get_hallucination_rate() == 0.0

    def test_rate_computed_correctly(self):
        """Rate = violations / total."""
        orch = Orchestrator("TEST-001")
        orch.total_blocks = 10
        orch.scope_violations = 3
        assert orch.get_hallucination_rate() == pytest.approx(0.3)
```

## Verification Plan

### Automated Tests

```bash
cd .agent && uv run pytest tests/core/implement/test_scope_guard.py -v
cd .agent && uv run pytest tests/core/implement/ -v
```

### Full Suite

```bash
cd .agent && uv run pytest -x --tb=short
```

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated with "Execution tracing and scope guardrails (INFRA-136)".

### Observability

- [ ] `scope_violation` structured log events emitted for blocked files.
- [ ] Langfuse trace spans emitted for each `apply_chunk()` call.
- [ ] Hallucination rate computed and set as span attribute.

### Testing

- [ ] All existing tests pass.
- [ ] 10 new tests covering extractors, scope guard, cross_cutting bypass, and hallucination rate.

## Copyright

Copyright 2026 Justin Cook.
