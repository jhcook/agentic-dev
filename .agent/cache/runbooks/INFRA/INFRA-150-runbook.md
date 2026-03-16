# STORY-ID: INFRA-150: Strict Block-Level Pydantic Rules

## State

ACCEPTED

## Goal Description

This task implements strict block-level validation for implementation runbooks to ensure that LLM-generated outputs do not contain "semantically empty" instructions. By enforcing non-empty Search/Replace pairs, mandatory code fences for new files, and meaningful rationales for deletions, we prevent silent execution failures and improve system reliability. Malformed blocks will now trigger explicit `ParsingError` or Pydantic `ValidationError` messages with clear context, facilitating faster debugging and prompt tuning.

## Linked Journeys

- JRN-057: Impact Analysis Workflow
- JRN-062: Implement Oracle Preflight Pattern

## Panel Review Findings

### @Architect
- **Verdict**: APPROVE
- **Summary**: The changes respect the existing model-parser boundary.
- **Findings**: The addition of `ParsingError` provides a specific exception type for structural failures that were previously handled via debug logging and no-op appends. This strengthens the contract between the parser and the executor.

### @Qa
- **Verdict**: APPROVE
- **Summary**: Validation rules now cover edge cases (whitespace-only blocks) that previously caused downstream issues.
- **Findings**:
  - AC-1 (Whitespace stripping/rejection) is enforced via Pydantic validators.
  - AC-2 (ModifyBlock requirement) is enforced via `model_validator`.
  - AC-3 (DeleteBlock rationale length) is already present in the model (`min_length=5`).
- **Required Changes**: Ensure integration tests in `test_parser.py` cover the new `ParsingError` scenarios.

### @Security
- **Verdict**: APPROVE
- **Summary**: No security regression. Stripping whitespace prevents bypass of "required" field checks via non-printing characters.
- **Findings**: `ParsingError` messages correctly include the block type and filename but do not leak PII or sensitive file content.

### @Product
- **Verdict**: APPROVE
- **Summary**: Rejects malformed LLM output early, which is essential for automation robustness.
- **Findings**: Acceptance criteria are clearly addressed in the implementation plan.

### @Observability
- **Verdict**: APPROVE
- **Summary**: `ParsingError` messages are structured and descriptive.
- **Findings**: Logs in `parser.py` are updated from debug to explicit exceptions, which will be captured in telemetry spans.

### @Docs
- **Verdict**: APPROVE
- **Summary**: Code changes include PEP-257 docstrings.
- **Findings**: The `ParsingError` class and updated validators are well-documented. Note: Ensure the `NEW` block validator docstring explicitly mentions whitespace stripping for consistency.

### @Compliance
- **Verdict**: APPROVE
- **Summary**: License headers are preserved in modified files. No GDPR/SOC2 impacts identified.

### @Backend
- **Verdict**: APPROVE
- **Summary**: Pydantic models use strict validation; `ParsingError` inheritance is correctly handled.
- **Findings**: Using `model_validator(mode="after")` ensures all fields are populated before complex structural checks.

## Codebase Introspection

### Targeted File Contents (from source)

#### .agent/src/agent/core/implement/models.py

```python
# Copyright 2026 Justin Cook
# ... (standard header)
"""Pydantic models for implementation runbook validation."""

from typing import List, Union, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
import os
from pathlib import Path
from agent.core.config import resolve_repo_path

class SearchReplaceBlock(BaseModel):
    """A single SEARCH/REPLACE pair within a MODIFY operation."""
    
    search: str = Field(..., min_length=1, description="The exact text to find.")
    replace: str = Field(..., description="The replacement text.")

    @field_validator("search")
    @classmethod
    def search_must_not_be_empty(cls, v: str) -> str:
        """Ensure search block is not just whitespace."""
        if not v.strip():
            raise ValueError("SEARCH block cannot be empty or only whitespace.")
        return v
...
```

#### .agent/src/agent/core/implement/parser.py

```python
# ... (imports)
from agent.core.implement.models import (
    RunbookSchema,
    RunbookStep,
    ModifyBlock,
    NewBlock,
    DeleteBlock,
    SearchReplaceBlock,
)
...
def _extract_runbook_data(content: str) -> List[dict]:
...
                if action == "MODIFY":
                    sr_blocks = []
                    # Also require >>> to be at start of line for robustness
                    sr_pattern = r'(?m)^<<<SEARCH\n(.*?)\n===\n(.*?)\n>>>[ \t]*$'
                    for sr in re.finditer(sr_pattern, block_body, re.DOTALL):
                        sr_blocks.append({"search": sr.group(1), "replace": sr.group(2)})
                    if not sr_blocks:
                        _logger.debug(f"Header found for {filepath} but no valid SEARCH/REPLACE blocks detected in body.")
                    operations.append({"path": filepath, "blocks": sr_blocks})

                elif action == "NEW":
                    # Use balanced detection for NEW content as it often contains ADRs with code fences
                    new_pattern = r'(?m)^( {0,3})(?P<fence>`{3,}|~{3,})[\w]*\n(.*?)\n\1(?P=fence)[ \t]*$'
                    fence_match = re.search(new_pattern, block_body, re.DOTALL)
                    file_content = fence_match.group(3).rstrip() if fence_match else ""
                    if not file_content:
                         _logger.debug(f"NEW block for {filepath} found but no balanced code fence matched in body.")
                    operations.append({"path": filepath, "content": file_content})
...
```

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| .agent/src/agent/core/implement/tests/test_models.py | N/A | Multiple validators | Add tests for whitespace stripping and empty rejection |
| .agent/src/agent/core/implement/tests/test_parser.py | N/A | `_extract_runbook_data` | Add tests for `ParsingError` on missing blocks or code fences |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| Search cannot be empty | `models.py` | `min_length=1` | Yes (and strip) |
| Replace cannot be empty | `models.py` | Allowed | NO (Reject empty per INFRA-150 AC-1) |
| Modify must have blocks | `models.py` | `min_length=1` | Yes |
| Delete rationale length | `models.py` | `min_length=5` | Yes |
| New content cannot be empty | `models.py` | Checked | Yes (and strip) |

## Implementation Steps

### Step 1: Update Pydantic models with strict validation and ParsingError

#### [MODIFY] .agent/src/agent/core/implement/models.py

```
<<<SEARCH
"""Pydantic models for implementation runbook validation."""

from typing import List, Union, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
===
"""Pydantic models for implementation runbook validation."""

from typing import List, Union, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
>>>
<<<SEARCH
from agent.core.config import resolve_repo_path

class SearchReplaceBlock(BaseModel):
    """A single SEARCH/REPLACE pair within a MODIFY operation."""
    
    search: str = Field(..., min_length=1, description="The exact text to find.")
    replace: str = Field(..., description="The replacement text.")

    @field_validator("search")
    @classmethod
    def search_must_not_be_empty(cls, v: str) -> str:
        """Ensure search block is not just whitespace."""
        if not v.strip():
            raise ValueError("SEARCH block cannot be empty or only whitespace.")
        return v
===
from agent.core.config import resolve_repo_path


class ParsingError(ValueError):
    """Raised when the runbook content cannot be parsed into the expected structure."""

    pass


class SearchReplaceBlock(BaseModel):
    """A single SEARCH/REPLACE pair within a MODIFY operation."""

    search: str = Field(..., min_length=1, description="The exact text to find.")
    replace: str = Field(..., description="The replacement text.")

    @field_validator("search")
    @classmethod
    def search_must_not_be_empty(cls, v: str) -> str:
        """Ensure search block is not just whitespace and strip it."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("SEARCH block cannot be empty or only whitespace.")
        return stripped

    @field_validator("replace")
    @classmethod
    def replace_must_not_be_empty(cls, v: str) -> str:
        """Ensure replace block is not just whitespace and strip it."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("REPLACE block cannot be empty or only whitespace.")
        return stripped
>>>
<<<SEARCH
class ModifyBlock(BaseModel):
    """An operation to modify an existing file."""
    
    path: str = Field(..., description="Repository-relative path to existing file.")
    blocks: List[SearchReplaceBlock] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_modify_path(self) -> "ModifyBlock":
        """Verify the path is valid for a modification."""
        if not self.path:
            raise ValueError("Path is required for MODIFY block.")
===
class ModifyBlock(BaseModel):
    """An operation to modify an existing file."""

    path: str = Field(..., description="Repository-relative path to existing file.")
    blocks: List[SearchReplaceBlock] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_modify_contents(self) -> "ModifyBlock":
        """Verify the block contains operations and the path is valid."""
        if not self.blocks:
            raise ValueError(
                "MODIFY block must contain at least one valid SEARCH/REPLACE block."
            )
        if not self.path:
            raise ValueError("Path is required for MODIFY block.")
>>>
<<<SEARCH
    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate new file content is non-empty and doesn't contain SEARCH blocks."""
        if not v.strip():
            raise ValueError("NEW file content cannot be empty.")
        # AC-5(b): NEW blocks must not contain <<<SEARCH blocks
        if "<<<SEARCH" in v:
            raise ValueError(
                "[NEW] file content must not contain <<<SEARCH blocks. "
                "Use [MODIFY] with search/replace instead."
            )
        return v
===
    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate new file content is non-empty (stripping whitespace) and doesn't contain SEARCH blocks."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("NEW file content cannot be empty.")
        # AC-5(b): NEW blocks must not contain <<<SEARCH blocks
        if "<<<SEARCH" in v:
            raise ValueError(
                "[NEW] file content must not contain <<<SEARCH blocks. "
                "Use [MODIFY] with search/replace instead."
            )
        return stripped
>>>
```

### Step 2: Update parser to raise ParsingError for empty headers

#### [MODIFY] .agent/src/agent/core/implement/parser.py

```
<<<SEARCH
from agent.core.implement.models import (
    RunbookSchema,
    RunbookStep,
    ModifyBlock,
    NewBlock,
    DeleteBlock,
    SearchReplaceBlock,
)
===
from agent.core.implement.models import (
    DeleteBlock,
    ModifyBlock,
    NewBlock,
    ParsingError,
    RunbookSchema,
    RunbookStep,
    SearchReplaceBlock,
)
>>>
<<<SEARCH
                if action == "MODIFY":
                    sr_blocks = []
                    # Also require >>> to be at start of line for robustness
                    sr_pattern = r'(?m)^<<<SEARCH\n(.*?)\n===\n(.*?)\n>>>[ \t]*$'
                    for sr in re.finditer(sr_pattern, block_body, re.DOTALL):
                        sr_blocks.append({"search": sr.group(1), "replace": sr.group(2)})
                    if not sr_blocks:
                        _logger.debug(f"Header found for {filepath} but no valid SEARCH/REPLACE blocks detected in body.")
                    operations.append({"path": filepath, "blocks": sr_blocks})

                elif action == "NEW":
                    # Use balanced detection for NEW content as it often contains ADRs with code fences
                    new_pattern = r'(?m)^( {0,3})(?P<fence>`{3,}|~{3,})[\w]*\n(.*?)\n\1(?P=fence)[ \t]*$'
                    fence_match = re.search(new_pattern, block_body, re.DOTALL)
                    file_content = fence_match.group(3).rstrip() if fence_match else ""
                    if not file_content:
                         _logger.debug(f"NEW block for {filepath} found but no balanced code fence matched in body.")
                    operations.append({"path": filepath, "content": file_content})
===
                if action == "MODIFY":
                    sr_blocks = []
                    # Also require >>> to be at start of line for robustness
                    sr_pattern = r'(?m)^<<<SEARCH\n(.*?)\n===\n(.*?)\n>>>[ \t]*$'
                    for sr in re.finditer(sr_pattern, block_body, re.DOTALL):
                        sr_blocks.append({"search": sr.group(1), "replace": sr.group(2)})
                    if not sr_blocks:
                        raise ParsingError(
                            f"MODIFY header for '{filepath}' found but no valid "
                            "SEARCH/REPLACE blocks detected in body."
                        )
                    operations.append({"path": filepath, "blocks": sr_blocks})

                elif action == "NEW":
                    # Use balanced detection for NEW content as it often contains ADRs with code fences
                    new_pattern = (
                        r'(?m)^( {0,3})(?P<fence>`{3,}|~{3,})[\w]*\n(.*?)\n\1(?P=fence)[ \t]*$'
                    )
                    fence_match = re.search(new_pattern, block_body, re.DOTALL)
                    file_content = fence_match.group(3).rstrip() if fence_match else ""
                    if not file_content:
                        raise ParsingError(
                            f"NEW header for '{filepath}' found but no balanced "
                            "code fence matched in body."
                        )
                    operations.append({"path": filepath, "content": file_content})
>>>
```

## Verification Plan

### Automated Tests

- [ ] `pytest .agent/src/agent/core/implement/tests/test_models.py` - Verify SearchReplaceBlock strips and rejects whitespace.
- [ ] `pytest .agent/src/agent/core/implement/tests/test_parser.py` - Verify `ParsingError` is raised for empty `[NEW]` or `[MODIFY]` headers, covering structural parser failures.

### Manual Verification

- [ ] Create a dummy runbook with a `#### [MODIFY]` header but no `<<<SEARCH` blocks and run `agent runbook validate --path <file>`. Expected output: Error message containing "no valid SEARCH/REPLACE blocks detected".
- [ ] Create a dummy runbook with a `#### [NEW]` header but no code block and run validation. Expected output: Error message containing "no balanced code fence matched".

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated to reflect the new strict validation rules and the breaking change where malformed blocks raise `ParsingError` instead of silent debug logging.
- [ ] Internal documentation for runbook authors updated to emphasize non-empty requirements for `REPLACE` blocks and the mandatory code fence structure for `NEW` blocks.

### Observability

- [ ] `ParsingError` includes file path and block type in the exception message.
- [ ] `validate_runbook_schema` captures and reports these errors in formatted output for APM visibility.

### Testing

- [ ] New unit tests cover all AC scenarios.
- [ ] Negative tests for whitespace-only search/replace/content fields pass.
- [ ] Integration tests verify the specific transition from logging to exception raising for the parser.

## Copyright

Copyright 2026 Justin Cook
