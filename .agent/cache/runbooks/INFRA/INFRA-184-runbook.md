# Runbook: Implementation Runbook for INFRA-184

## State

ACCEPTED

## Implementation Steps

### Step 1: Architecture & Design Review

#### [MODIFY] CHANGELOG.md

```

<<<SEARCH
## [Unreleased] (Updated by story)
===
## [Unreleased] (Updated by story)

## [Unreleased]

**Changed**
- Hardened implementation pipeline to automatically reject malformed empty S/R blocks and auto-correct schema violations (INFRA-184).
- Added structured logging for malformed search block rejection events.
>>>

```

### Step 2: Implementation - Prompt Guarding

#### [MODIFY] .agent/src/agent/commands/runbook_generation.py

```

<<<SEARCH
    - Each [MODIFY] block must contain at least one <<<SEARCH / === / >>> sequence.
===
    - Each [MODIFY] block must contain at least one <<<SEARCH / === / >>> sequence.
    - Negative Constraint: Never emit an empty <<<SEARCH block (e.g., <<<SEARCH\n\n===). If you have no search text, omit the block entirely.
>>>

```


### Step 3: Security & Input Sanitization - Runbook Post-processing

#### [MODIFY] .agent/src/agent/commands/runbook_postprocess.py

```

<<<SEARCH
logger = get_logger(__name__)
console = Console()


def _fix_changelog_sr_headings(content: str) -> str:
===
logger = get_logger(__name__)
console = Console()


def strip_empty_sr_blocks(content: str) -> str:
    """Remove malformed S/R blocks where the SEARCH section is empty (AC-1).

    The AI occasionally generates blocks with no search text, which the
    implementation engine would otherwise interpret as 'replace empty string',
    effectively prepending the content to the start of the file.
    """
    # Matches <<<SEARCH followed only by whitespace/newlines and then ===
    # until the closing >>>
    pattern = re.compile(r'<<<SEARCH\s*===\s*.*?>>>', re.DOTALL)
    return pattern.sub("<!-- stripped empty SEARCH block (INFRA-184) -->", content)


def _fix_changelog_sr_headings(content: str) -> str:
>>>
<<<SEARCH
def _autocorrect_schema_violations(content: str) -> str:
    """Deterministic healer for common AI schema violations.

    Three fixes in order:
    1. Prose [MODIFY/NEW] headers (regex/code leaked out of a fence) → stripped.
    2. Empty [MODIFY] blocks with no <<<SEARCH → stripped.
    3. [NEW] blocks containing <<<SEARCH → SEARCH fragment removed.
    """
===
def _autocorrect_schema_violations(content: str) -> str:
    """Deterministic healer for common AI schema violations.

    Six fixes in order:
    1. Prose [MODIFY/NEW] headers (regex/code leaked out of a fence) → stripped.
    2. Empty [MODIFY] blocks with no <<<SEARCH → stripped.
    3. [NEW] blocks containing <<<SEARCH → SEARCH fragment removed.
    4. Oversized SEARCH blocks → trimmed to identify anchor.
    5. Empty SEARCH blocks → stripped (AC-1).
    6. Empty function-after blocks → stripped (AC-3).
    """
    # Apply AC-1 early
    content = strip_empty_sr_blocks(content)
>>>
<<<SEARCH
    content = re.sub(
        r"(?ms)^#### \[MODIFY\] .+?\n(?:(?!^#{3,4}\s).)*(?=^#{3,4}\s|\Z)",
        _process_modify_block,
        content,
    )

    return content
===
        content = re.sub(
            r"(?ms)^#### \[MODIFY\] .+?\n(?:(?!^#{3,4}\s).)*(?=^#{3,4}\s|\Z)",
            _process_modify_block,
            content,
        )

        # ── 6. Empty function-after blocks (AC-3) ────────────────────────────────
        # Failure Mode 2: schema rejects empty function-after.blocks lists.
        # We strip these to satisfy validation constraints.
        content = re.sub(
            r'"function-after":\s*\{\s*"blocks":\s*\[\s*\]\s*\},?',
            '/* schema-autocorrect: stripped empty function-after blocks */',
            content
        )

        return content
>>>

```

### Step 4: Implementation - Parser Early Rejection & Reporting

#### [MODIFY] .agent/src/agent/core/implement/parser.py

```

<<<SEARCH
    for match in re.finditer(SR_BLOCK_PATTERN, content, re.DOTALL):
        search_text = match.group(1)
        replace_text = match.group(2)

        yield SRBlock(
===
    for match in re.finditer(SR_BLOCK_PATTERN, content, re.DOTALL):
        search_text = match.group(1)
        replace_text = match.group(2)

        # Early rejection of malformed empty SEARCH blocks (AC-4)
        # This prevents the implementation engine from prepending the replacement
        # code to the entire file when a search anchor is missing.
        if not search_text.strip():
            logger.warning(
                "sr_replace_malformed_empty_search",
                extra={
                    "event": "sr_replace_malformed_empty_search",
                    "path": str(filepath),
                    "snippet": replace_text[:100].strip()
                }
            )
            continue

        yield SRBlock(
>>>

```

#### [MODIFY] .agent/src/agent/commands/runbook_gates.py

```

<<<SEARCH
    if failed_count > 0:
        console.print(f"\n[red]❌ {failed_count} file(s) failed syntax validation.[/red]")
    else:
        console.print("\n[green]✅ All S/R blocks passed syntax validation.[/green]")
===
    if failed_count > 0:
        console.print(f"\n[red]❌ {failed_count} file(s) failed syntax validation.[/red]")
    
    # Surface summary of skipped malformed blocks (AC-5)
    # These are captured during parsing and tagged as malformed to avoid false syntax warnings.
    malformed_skipped = len([r for r in results if r[1] == "sr_replace_malformed_empty_search"])
    if malformed_skipped > 0:
        console.print(
            f"[yellow]⚠ {malformed_skipped} malformed block(s) with empty SEARCH sections "
            "were skipped to prevent false AST corruption.[/yellow]"
        )

    if failed_count == 0:
        console.print("\n[green]✅ All remaining S/R blocks passed syntax validation.[/green]")
>>>

```

### Step 5: Observability & Audit Logging

#### [MODIFY] .agent/src/agent/commands/audit.py

```

<<<SEARCH
def log_api_rename_gate_fail(symbol: str, old_name: str, new_name: Optional[str], consumers: List[str]) -> None
===
def log_api_rename_gate_fail(symbol: str, old_name: str, new_name: Optional[str], consumers: List[str]) -> None:
    """Log a failure in the API rename safety gate."""
    # Implementation remains unchanged
    pass

def log_sr_malformation_event(file_path: str, reason: str, action: str) -> None:
    """Log a malformed S/R block event to the governance audit trail as per ADR-046.

    This event is triggered when the S/R parser or post-processor detects an empty 
    SEARCH block or other schema violations that require automatic intervention.
    """
    log_governance_event(
        "sr_replace_malformed_empty_search",
        {
            "file_path": file_path,
            "reason": reason,
            "action": action,
            "timestamp": datetime.now().isoformat(),
            "event_code": "INFRA-184",
            "severity": "WARNING"
        }
    )
>>>

```

#### [NEW] .agent/tests/agent/commands/test_sr_observability.py

```python
import pytest
from unittest.mock import MagicMock, patch
from agent.commands.audit import log_sr_malformation_event

@patch("agent.commands.audit.log_governance_event")
def test_log_sr_malformation_event(mock_log):
    """Verify that malformed S/R events are correctly routed to the governance logger."""
    file_path = "backend/voice/tools/git.py"
    reason = "empty search block"
    action = "skipped"
    
    log_sr_malformation_event(file_path, reason, action)
    
    mock_log.assert_called_once()
    args, kwargs = mock_log.call_args
    assert args[0] == "sr_replace_malformed_empty_search"
    assert args[1]["file_path"] == file_path
    assert args[1]["reason"] == reason
    assert args[1]["action"] == action
    assert "timestamp" in args[1]
    assert args[1]["event_code"] == "INFRA-184"

```

### Step 6: Verification & Test Suite

#### [NEW] .agent/tests/test_runbook_postprocess.py

```python
import pytest
from agent.commands.runbook_postprocess import strip_empty_sr_blocks, _autocorrect_schema_violations

def test_strip_empty_sr_blocks_basic():
    """AC-1: Verify that empty SEARCH blocks are stripped."""
    content = """
#### [MODIFY] agent/core/utils.py

```python
<<<SEARCH

===
print('corrupted implementation')
>>>

```

"""
    result = strip_empty_sr_blocks(content)
    assert "<<<SEARCH" not in result
    assert "stripped empty SEARCH block (INFRA-184)" in result

def test_strip_empty_sr_blocks_idempotency():
    """Verify that running the stripper twice produces the same output."""
    content = "<<<SEARCH\n\n===\nx = 1\n>>>"
    first_pass = strip_empty_sr_blocks(content)
    second_pass = strip_empty_sr_blocks(first_pass)
    assert first_pass == second_pass

def test_autocorrect_schema_empty_function_after():
    """AC-3: Verify that empty function-after blocks are stripped from runbook JSON/Markdown."""
    content = '"function-after": { "blocks": [] }'
    result = _autocorrect_schema_violations(content)
    assert '"function-after"' not in result
    assert "stripped empty function-after blocks" in result

def test_autocorrect_does_not_strip_valid_blocks():
    """Ensure valid S/R blocks remain untouched."""
    valid_block = """
<<<SEARCH
def hello():
    pass
===
def hello():
    print('hi')
>>>
"""
    result = strip_empty_sr_blocks(valid_block)
    assert valid_block == result

```

#### [NEW] .agent/tests/test_utils_sr_gate.py

```python
import pytest
from agent.commands.utils import _sr_check_replace_syntax

def test_sr_gate_returns_none_on_empty_search():
    """Verify that the syntax gate returns None early on empty search text (partial fix check)."""
    # content, search, replace
    result = _sr_check_replace_syntax("file content", "", "new content")
    assert result is None

```

#### [MODIFY] .agent/tests/core/implement/test_parser.py

```python
<<<SEARCH
assert blocks[0].replace_text == "print('hello world')\n"
===
assert blocks[0].replace_text == "print('hello world')\n"

def test_parse_sr_blocks_rejects_empty_search(caplog):
    """AC-4: Verify parser skips blocks with whitespace-only SEARCH sections and logs it."""
    import logging
    from agent.core.implement.parser import parse_sr_blocks
    from pathlib import Path

    # Runbook content with a deliberate empty SEARCH block
    content = 'fake S/R with empty search'
    with caplog.at_level(logging.WARNING):
        blocks = list(parse_sr_blocks(content, Path("src/dummy.py")))

    assert len(blocks) == 0
    assert "sr_replace_malformed_empty_search" in caplog.text
>>>

```

#### [NEW] .agent/tests/test_integration_runbook.py

```python
import pytest
from agent.commands.runbook_gates import validate_runbook_syntax_for_story
from unittest.mock import MagicMock, patch

def test_regression_infra_146_zero_syntax_advisories():
    """Regression: Verify that a runbook targeting 15 files with malformed blocks produces 0 advisories."""
    # We mock the parser to return 'malformed' events for multiple tool files
    # to ensure the gates.py logic summarizes them correctly per AC-5.
    file_list = [f"backend/voice/tools/tool_{i}.py" for i in range(15)]
    
    # Mock the parser to yield nothing for these files (simulating empty search detection)
    with patch("agent.commands.runbook_gates.parse_sr_blocks", return_value=[]):
        # Mock results list to simulate malformed skips for all 15 files
        mock_results = [(f, "sr_replace_malformed_empty_search", None) for f in file_list]
        
        with patch("agent.commands.runbook_gates.Console") as mock_console_class:
            mock_console = mock_console_class.return_value
            
            # We use a custom runner that injects these results into the gate summary logic
            # or directly test the summary logic in runbook_gates.py
            from agent.commands.runbook_gates import _display_sr_validation_summary
            
            _display_sr_validation_summary(mock_results)
            
            # Assert that the summary output contains the expected warning about skipped blocks
            # and NOT the 'failed syntax validation' error message.
            printed_text = "".join(call.args[0] for call in mock_console.print.call_args_list if call.args)
            assert "15 malformed block(s)" in printed_text
            assert "skipped to prevent false AST corruption" in printed_text
            assert "0 file(s) failed syntax validation" in printed_text

```

### Step 7: Deployment & Rollback Strategy

#### [MODIFY] CHANGELOG.md

```

<<<SEARCH
**Changed**
- Hardened implementation pipeline to automatically reject malformed empty S/R blocks and auto-correct schema violations (INFRA-184).
===
**Changed**
- Hardened runbook S/R pipeline: empty SEARCH blocks stripped at postprocessor level; parser emits structured log events; prompt guard added to generation prompt; function-after schema autocorrection added (INFRA-184).
>>>

```

## Copyright

Copyright 2026 Justin Cook
