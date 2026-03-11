# STORY-ID: INFRA-117: Improve Implement Error Hints

## State

ACCEPTED

## Goal Description

Improve the diagnostic feedback of the `agent implement` command by replacing generic error hints with context-aware, specific exceptions.

## Linked Journeys

- JRN-088: Console Agentic Tool Capabilities
- JRN-096: Safe Implementation Apply

## Panel Review Findings

- **@Architect**: Moving from boolean return values to typed exceptions in the guards improves robust propagation of failure reasons.
- **@Qa**: Needs tests for the "hint" string output.

## Codebase Introspection

Files examined: `.agent/src/agent/core/implement/guards.py`, `.agent/src/agent/core/implement/orchestrator.py`

## Implementation Steps

### Step 1: Define FileSizeGuardViolation and update guards.py

#### [MODIFY] .agent/src/agent/core/implement/guards.py

```python
<<<SEARCH
FILE_SIZE_GUARD_THRESHOLD: int = 200
SOURCE_CONTEXT_MAX_LOC: int = 300
SOURCE_CONTEXT_HEAD_TAIL: int = 100

_console = Console()
===
FILE_SIZE_GUARD_THRESHOLD: int = 200
SOURCE_CONTEXT_MAX_LOC: int = 300
SOURCE_CONTEXT_HEAD_TAIL: int = 100

class ImplementGuardViolation(Exception):
    """Base class for all implementation guard violations."""
    pass

class FileSizeGuardViolation(ImplementGuardViolation):
    """Raised when a file change violates the size safety threshold."""
    pass

class DocstringGuardViolation(ImplementGuardViolation):
    """Raised when a file change lacks required PEP-257 docstrings."""
    pass

_console = Console()
>>>
<<<SEARCH
    if file_path.exists() and not legacy_apply:
        try:
            existing_lines = len(file_path.read_text().splitlines())
        except Exception:
            existing_lines = 0
        if existing_lines > FILE_SIZE_GUARD_THRESHOLD:
            _console.print(
                f"\n[bold red]❌ Rejected full-file overwrite for {filepath} "
                f"({existing_lines} LOC > {FILE_SIZE_GUARD_THRESHOLD} threshold).[/bold red]"
            )
            logging.warning(
                "apply_change apply_mode=rejected file=%s file_loc=%d threshold=%d",
                filepath, existing_lines, FILE_SIZE_GUARD_THRESHOLD,
            )
            if span_ctx:
                span_ctx.set_attribute("success", False)
                span_ctx.end()
            return False
===
    if file_path.exists() and not legacy_apply:
        try:
            existing_lines = len(file_path.read_text().splitlines())
        except Exception:
            existing_lines = 0
        if existing_lines > FILE_SIZE_GUARD_THRESHOLD:
            if span_ctx:
                span_ctx.set_attribute("success", False)
                span_ctx.end()
            raise FileSizeGuardViolation(
                f"File '{filepath}' already exists and new content is {existing_lines} lines. "
                f"Maximum allowed for full-file replace is {FILE_SIZE_GUARD_THRESHOLD} LOC. "
                "Hint: Update runbook step to use <<<SEARCH/===/>>> blocks for incremental changes."
            )
>>>
```

### Step 2: Handle exceptions in orchestrator.py

#### [MODIFY] .agent/src/agent/core/implement/orchestrator.py

```python
<<<SEARCH
            # AC-9 bug fix: initialise block_loc to 0 before each apply call
            block_loc = 0
            success = apply_change_to_file(
                block["file"], block["content"], self.yes,
                legacy_apply=self.legacy_apply,
            )
            if success:
                block_loc = count_edit_distance(original_content, block["content"])
                step_modified_files.append(block["file"])
            else:
                self.rejected_files.append(block["file"])
                _console.print(
                    f"[bold yellow]⚠️  INCOMPLETE STEP: {block['file']} was not applied. "
                    f"Update the runbook step to use <<<SEARCH/===/>>> format.[/bold yellow]"
                )
            step_loc += block_loc
===
            # AC-9 bug fix: initialise block_loc to 0 before each apply call
            block_loc = 0
            
            from agent.core.implement.guards import FileSizeGuardViolation
            try:
                success = apply_change_to_file(
                    block["file"], block["content"], self.yes,
                    legacy_apply=self.legacy_apply,
                )
            except FileSizeGuardViolation as e:
                success = False
                self.rejected_files.append(block["file"])
                _console.print(
                    f"[bold red]❌ SIZE GUARD GATE: {block['file']} rejected. "
                    f"{str(e)}[/bold red]"
                )
                
            if success:
                block_loc = count_edit_distance(original_content, block["content"])
                step_modified_files.append(block["file"])
            elif block["file"] not in self.rejected_files:
                self.rejected_files.append(block["file"])
                _console.print(
                    f"[bold yellow]⚠️  INCOMPLETE STEP: {block['file']} was not applied. "
                    f"Update the runbook step to use <<<SEARCH/===/>>> format.[/bold yellow]"
                )
            step_loc += block_loc
>>>
<<<SEARCH
            _console.print(
                "[yellow]Hint: update runbook step(s) to use "
                "<<<SEARCH\n<exact lines>\n===\n<replacement>\n>>> blocks "
                "then re-run `agent implement`.[/yellow]"
            )
===
            _console.print(
                "[yellow]Hint: Review the specific rejection reasons above. You may need to add "
                "missing docstrings or use <<<SEARCH/===/>>> blocks for large file mutations.[/yellow]"
            )
>>>
```

### Step 3: Add Unit Tests

#### [NEW] .agent/tests/core/implement/test_errors.py

```python
"""Tests for implementation error handling and guard violations."""

import pytest
from agent.core.implement.guards import (
    check_file_size_guard,
    FileSizeGuardViolation,
    FILE_SIZE_GUARD_THRESHOLD,
    apply_change_to_file
)

def test_file_size_guard_violation(tmp_path):
    """Verify that exceeding the LOC threshold raises FileSizeGuardViolation with a hint."""
    target_file = tmp_path / "large_file.py"
    target_file.write_text("existing content\n" * 5)
    
    # Create content exceeding threshold
    large_content = "\n".join(["print('test')"] * (FILE_SIZE_GUARD_THRESHOLD + 1))
    
    with pytest.raises(FileSizeGuardViolation) as excinfo:
        apply_change_to_file(str(target_file), large_content, yes=True)
    
    assert "already exists and new content is" in str(excinfo.value)
    assert "incremental changes" in str(excinfo.value)

def test_file_size_guard_new_file_allowed(tmp_path):
    """Verify that a non-existent file is allowed even if it is large (it's not an overwrite)."""
    target_file = tmp_path / "new_large_file.py"
    large_content = "\n".join(["print('test')"] * (FILE_SIZE_GUARD_THRESHOLD + 1))
    
    # Should NOT raise because path.exists() is False
    result = apply_change_to_file(str(target_file), large_content, yes=True)
    assert result is True

```

## Verification Plan

- Run new tests: `pytest .agent/tests/core/implement/test_errors.py`
- Run existing orchestrator tests: `pytest .agent/tests/core/implement/test_orchestrator.py`

## Definition of Done

- All existing tests pass.
- New unit tests cover `FileSizeGuardViolation`.

## Copyright

Copyright 2026 Justin Cook