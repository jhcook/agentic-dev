# Runbook: Implementation Runbook for INFRA-182: Generation-Time SEARCH Block Verbatim Verification

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

**Added**
- Automated generation-time verification for `<<<SEARCH` blocks to ensure verbatim parity with on-disk source code (INFRA-182).
>>>

```

### Step 2: Implementation: SEARCH Block Post-Processing

#### [MODIFY] .agent/src/agent/commands/runbook_generation.py

```

<<<SEARCH
import json
import os
import re
import time
===
import json
import os
import re
import time
import difflib
>>>

```

<!-- DEDUP: .agent/src/agent/commands/runbook_generation.py already [MODIFY] in Step 1. All changes for this file should be consolidated there. -->

#### [MODIFY] headers and their bodies until next section header
    pattern = re.compile(
        r'####\s+\[MODIFY\]\s+([^\n`]+).*?\n(?:(?!####\s+\[|###\s+|\Z).)*',
        re.DOTALL,
    )
    result = pattern.sub(_modify_section_replacer, content)

    if total_corrected > 0 or total_unresolved > 0:
        summary = []
        if total_corrected:
            summary.append(f"[green]✅ {total_corrected} block(s) corrected to verbatim match.[/green]")
        if total_unresolved:
            summary.append(f"[yellow]⚠️  {total_unresolved} block(s) unresolved and flagged.[/yellow]")
        console.print(" ".join(summary))

    return result
>>>

```

<!-- DEDUP: .agent/src/agent/commands/runbook_generation.py already [MODIFY] in Step 1. All changes for this file should be consolidated there. -->

```

### Step 3: Security & Input Sanitization

#### [MODIFY] .agent/src/agent/core/implement/sr_validation.py

```

<<<SEARCH
# Resolve file path
        resolved = repo_root / filepath
        if not resolved.exists():
            continue  # NEW file — nothing to validate against

        actual_content = resolved.read_text()
===
# Resolve and validate file path (security check: prevent path traversal)
        try:
            resolved = (repo_root / filepath).resolve()
            # Strict enforcement: target must be inside repo_root
            if not str(resolved).startswith(str(repo_root.resolve())):
                logging.warning(
                    "sr_validation_path_traversal_blocked",
                    extra={"path": filepath, "repo_root": str(repo_root)}
                )
                continue
        except (OSError, ValueError):
            continue

        if not resolved.exists() or not resolved.is_file():
            continue  # NEW file or directory — nothing to validate against

        # Strictly read-only operation as per INFRA-182 requirement
        actual_content = resolved.read_text(encoding="utf-8")
>>>

```

### Step 4: Observability & Audit Logging

### Step 5: Documentation Updates

#### [NEW] .agent/docs/user-guide/runbooks.md

```markdown
# Runbook Implementation Guide

**Automated SEARCH Verification**

The runbook generation pipeline includes an automated verbatim verification step for all `[MODIFY]` blocks. This step ensures that the code snippets provided by the AI as search anchors actually exist in the target files, absorbing common hallucinations such as indentation drift or minor syntax variations.

**How it Works**

After Implementation blocks are generated in Phase 2, a post-processing pass reads target files from disk and compares the generated `<<<SEARCH` content against the actual file content.

1. **Fuzzy Matching**: The processor utilizes a sliding-window fuzzy matcher (SequenceMatcher) to find the most similar region in the target file.
2. **Verbatim Correction**: If a match is found with a similarity score of 0.7 (70%) or higher, the hallucinated text in the runbook is automatically replaced with the exact verbatim content from disk.
3. **Unresolved Flags**: If no region meets the 0.7 similarity threshold, the block is preserved as-is but is annotated with the `# SEARCH_UNRESOLVED` marker.

**Handling # SEARCH_UNRESOLVED**

The `# SEARCH_UNRESOLVED` annotation appears at the top of a code block when the automated verification step fails to find a high-confidence match for the AI-generated search text. This serves as a hard flag for the human reviewer.

**Expected Developer Response**:
- **Manual Verification**: You MUST manually inspect any block containing this marker.
- **Correction**: Open the target file, locate the intended change area, and copy the relevant lines verbatim into the `<<<SEARCH` section of the runbook.
- **Validation**: Ensure the marker is removed or addressed before running `agent implement --apply`, as unresolved blocks will likely cause implementation failures.

**Troubleshooting**

- **Incorrect File Path**: Ensure the file path provided in the `#### [MODIFY]` header is correct and relative to the repository root. If the file does not exist, the verification step is skipped (intended for `[NEW]` files).
- **Ambiguous Search**: If a file contains multiple identical code segments, the AI might not provide enough context for a unique match. Adding surrounding lines to the SEARCH block manually will resolve this.
- **Low Similarity**: If the AI's version of the code is too different from the actual file (e.g., targeting a drastically outdated version), the fuzzy matcher will fail. Use the actual file content as the ground truth.

```

### Step 6: Verification & Test Suite

#### [MODIFY] .agent/tests/commands/test_runbook_generation.py

```

<<<SEARCH
with patch("pathlib.Path.exists", return_value=False), patch("pathlib.Path.read_text", return_value=""), patch("pathlib.Path.write_text"):
        raw = generate_runbook_chunked("INFRA-174", "story", "rules", "context", "tree", "code")
        
    assert "[Aborted: Pass 1 Failed]" in raw
===
with patch("pathlib.Path.exists", return_value=False), patch("pathlib.Path.read_text", return_value=""), patch("pathlib.Path.write_text"):
        raw = generate_runbook_chunked("INFRA-174", "story", "rules", "context", "tree", "code")
        
    assert "[Aborted: Pass 1 Failed]" in raw


@patch("agent.core.implement.sr_validation.Path.exists")
@patch("agent.core.implement.sr_validation.Path.read_text")
@patch("agent.core.implement.sr_validation.get_logger")
def test_sr_validation_verbatim_replacement(mock_get_logger, mock_read, mock_exists):
    """AC-1 & AC-4: Successful verbatim replacement and logging for high-similarity matches."""
    from agent.core.implement.sr_validation import validate_and_correct_sr_blocks
    mock_exists.return_value = True
    # Ground truth on disk has specific indentation and content
    mock_read.return_value = "class Foo:\n    def bar(self):\n        return True\n"
    mock_logger = mock_get_logger.return_value

    # LLM approximated SEARCH (missing class indentation)
    runbook_content = (
        "#### [MODIFY] .agent/src/agent/foo.py\n"

```python
        "```python\n"
        "<<<SEARCH\ndef bar(self):\n    return True\n"
        "===\ndef bar(self):\n    return False\n"
        ">>>\n```"
    )

    # Similarity will be > 0.7 due to SequenceMatcher logic
    corrected, total, fixed = validate_and_correct_sr_blocks(runbook_content, threshold=0.7)

    assert total == 1
    assert fixed == 1
    # Should have replaced with verbatim content from mock_read
    assert "<<<SEARCH\n    def bar(self):\n        return True\n" in corrected
    assert "was_corrected": True in str(mock_logger.info.call_args_list)


@patch("agent.core.implement.sr_validation.Path.exists")
@patch("agent.core.implement.sr_validation.Path.read_text")
@patch("agent.core.implement.sr_validation._ai_reanchor_search")
def test_sr_validation_unresolved_annotation(mock_ai, mock_read, mock_exists):
    """AC-2: Correct application of # SEARCH_UNRESOLVED for low-similarity matches."""
    from agent.core.implement.sr_validation import validate_and_correct_sr_blocks
    mock_exists.return_value = True
    mock_read.return_value = "def unrelated_logic():\n    pass\n"
    mock_ai.return_value = None  # AI re-anchor also fails

    runbook_content = (
        "

```

<!-- DEDUP: .agent/src/agent/foo.py\n" already [MODIFY] in Step 1. All changes for this file should be consolidated there. -->

#### [MODIFY] .agent/src/agent/new_file.py\n"
        "```python\n"
        "<<<SEARCH\n\n===\ncontent\n>>>\n```"
    )

    corrected, total, fixed = validate_and_correct_sr_blocks(runbook_content)

    assert total == 0
    assert fixed == 0
    assert corrected == runbook_content

@patch("agent.core.ai.ai_service.complete")
def test_generation_pipeline_suppresses_failure_output(mock_complete, capsys):
    """AC-5: Verification that no 'failed' message is printed when all blocks are corrected."""
    from agent.commands.runbook_generation import generate_runbook_chunked
    import json
    
    # Mock successful Phase 1 and Phase 2
    mock_complete.side_effect = [
        json.dumps({"title": "T", "sections": [{"title": "S1", "files": ["f1.py"]}]}),
        json.dumps({"header": "S1", "ops": [{"op": "modify", "file": "f1.py", "search": "old", "replace": "new"}]})
    ]

    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.read_text", return_value="old\n"), \
         patch("pathlib.Path.write_text"):
        
        # Force a run
        generate_runbook_chunked("INFRA-182", "story", "rules", "context", "tree", "code")
        
    captured = capsys.readouterr()
    # The implementation should print a success message instead of a failure message
    assert "block(s) corrected to verbatim" in captured.out
    assert "S/R block(s) still failed" not in captured.out
>>>

```



### Step 7: Deployment & Rollback Strategy
