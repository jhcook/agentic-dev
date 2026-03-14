# INFRA-134: Shift-Left Runbook Validation with Pydantic

## State

ACCEPTED

## Goal Description

Runbook validation is currently prone to hallucinations and structural errors because it relies on regex-based parsing. This task replaces the legacy validation with strict Pydantic models and implements a self-correction loop (ADR-012) in the runbook generation command. By validating the AI's output against a strict schema before writing to disk, we ensure that all generated runbooks are machine-executable and reduce implementation failures.

## Linked Journeys

- JRN-065: Runbook Generation and Implementation

## Panel Review Findings

### @Architect
- **Pydantic V2**: Excellent choice for performance and strict typing.
- **Decoupling**: Defining models in a dedicated `models.py` ensures validation logic is reusable by both the generator and the executor.
- **Self-Correction**: Implementing the retry loop directly in the command respects ADR-012 and ADR-005.

### @Qa
- **Negative Testing**: The validator must explicitly catch empty `SEARCH` blocks and missing replacement content, which were previously missed by regex.
- **Test Matrix**: Existing tests in `test_parser.py` expect a specific list of strings for violations. We must ensure the new Pydantic-based `validate_runbook_schema` maintains this interface (returning `List[str]`) for backward compatibility or update the tests.

### @Security
- **Path Traversal**: Validators must ensure that file paths in the runbook are relative to the project root and do not attempt to escape via `..`.
- **PII**: Ensure that `ValidationError` messages from Pydantic are scrubbed before being logged or displayed if they contain snippet content.

### @Product
- **User Experience**: The iterative retry loop significantly reduces "failed-at-the-finish-line" experiences where a runbook is generated but fails to apply.
- **Actionable Errors**: Pydantic's error messages should be formatted for the LLM to understand what exactly was wrong.

### @Observability
- **Structured Logging**: Log each validation attempt, including the error details and the attempt count. This allows us to track "Prompt Drift" where the LLM starts failing the schema more frequently.

### @Docs
- **Internal API**: The `models.py` module must be fully documented as it becomes a core part of the implementation engine.

### @Compliance
- **License Headers**: Standard Apache 2.0 headers are required on the new `models.py`.

### @Backend
- **Strict Typing**: Use Pydantic's `Annotated` and `Field` for maximum schema clarity.
- **PEP-257**: All new functions and classes must have descriptive docstrings.

## Codebase Introspection

### Targeted File Contents (from source)

- `.agent/src/agent/commands/runbook.py`: Contains the `new_runbook` command and the current call to `validate_runbook_schema`.

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| `.agent/tests/test_runbook.py` | `agent.commands.runbook.validate_runbook_schema` | `agent.core.implement.parser.validate_runbook_schema` | Ensure the command correctly handles the new return types and retries. |
| `.agent/tests/test_parser.py` | `agent.core.implement.parser.validate_runbook_schema` | Same | Update tests to verify Pydantic's more granular error reporting. |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| `validate_runbook_schema` returns `List[str]` | `test_parser.py` | List of violation strings | Yes, for CLI output consistency. |
| Runbook generation requires `COMMITTED` state | `runbook.py` | `re.search(state_pattern, ...)` | Yes. |

## Targeted Refactors & Cleanups (INFRA-043)

- [x] Remove legacy regex-based path validation from `parser.py` once Pydantic is active.
- [x] Consolidate block parsing logic to use the new models.

## Implementation Steps

### Step 1: Create Pydantic models for runbook structure

Define the core building blocks of a runbook (Modify, New, Delete, Step) using Pydantic V2. This includes custom validators for the specific requirements of the story (non-empty search, valid path directories).

#### [NEW] .agent/src/agent/core/implement/models.py

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

"""Pydantic models for implementation runbook validation."""

from typing import List, Union, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
import os
from pathlib import Path

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

class ModifyBlock(BaseModel):
    """An operation to modify an existing file."""
    
    path: str = Field(..., description="Repository-relative path to existing file.")
    blocks: List[SearchReplaceBlock] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_modify_path(self) -> "ModifyBlock":
        """Verify the path is valid for a modification."""
        if not self.path:
            raise ValueError("Path is required for MODIFY block.")
        # Basic relative path safety
        if ".." in self.path or self.path.startswith("/"):
            raise ValueError(f"Path must be repository-relative and safe: {self.path}")
        return self

class NewBlock(BaseModel):
    """An operation to create a new file."""
    
    path: str = Field(..., description="Repository-relative path for the new file.")
    content: str = Field(..., min_length=1, description="Complete file content.")

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        """Ensure new file content is not empty."""
        if not v.strip():
            raise ValueError("NEW file content cannot be empty.")
        return v

class DeleteBlock(BaseModel):
    """An operation to remove a file."""
    
    path: str = Field(..., description="Repository-relative path to delete.")
    rationale: str = Field(..., min_length=5, description="Rationale for deletion.")

class RunbookStep(BaseModel):
    """A logical step in the implementation containing one or more operations."""
    
    title: str = Field(..., min_length=5, description="Step title.")
    operations: List[Union[ModifyBlock, NewBlock, DeleteBlock]] = Field(..., min_length=1)

class RunbookSchema(BaseModel):
    """The complete structure of a runbook implementation section."""
    
    steps: List[RunbookStep] = Field(..., min_length=1)
```

### Step 2: Implement the self-correction retry loop in runbook generation

Modify the `new_runbook` command to validate the AI response using Pydantic. If validation fails, feed the error back to the LLM for up to 3 attempts.

#### [MODIFY] .agent/src/agent/commands/runbook.py

```
<<<SEARCH
    console.print("[bold green]🤖 Panel is discussing...[/bold green]")
    with console.status("[bold green]🤖 Panel is discussing...[/bold green]") as status:
        content = ai_service.complete(system_prompt, user_prompt, rich_status=status)
        
    if not content:
        console.print("[bold red]❌ AI returned empty response.[/bold red]")
        raise typer.Exit(code=1)
===
    console.print("[bold green]🤖 Panel is discussing...[/bold green]")
    
    max_attempts = 3
    attempt = 0
    content = ""
    current_user_prompt = user_prompt

    while attempt < max_attempts:
        attempt += 1
        with console.status(f"[bold green]🤖 Panel is discussing (Attempt {attempt}/{max_attempts})...[/bold green]") as status:
            content = ai_service.complete(system_prompt, current_user_prompt, rich_status=status)
            
        if not content:
            console.print("[bold red]❌ AI returned empty response.[/bold red]")
            raise typer.Exit(code=1)

        # -- SPLIT_REQUEST Fallback (INFRA-094) --
        if "SPLIT_REQUEST" in content:
            break # Let the split logic below handle it

        # Schema validation (AC-3)
        schema_violations = validate_runbook_schema(content)
        if not schema_violations:
            break
            
        logger.warning(
            "runbook_validation_fail attempt=%d story=%s errors=%d",
            attempt, story_id, len(schema_violations)
        )
        
        if attempt < max_attempts:
            error_msg = "\n".join([f"- {v}" for v in schema_violations])
            console.print(f"[yellow]⚠️  Attempt {attempt} failed validation. Asking for correction...[/yellow]")
            current_user_prompt = (
                f"{user_prompt}\n\n"
                f"### SCHEMA VALIDATION FAILED ON PREVIOUS ATTEMPT ###\n"
                f"Your previous output had the following violations:\n{error_msg}\n\n"
                f"Please correct these errors and generate the full runbook again."
            )
        else:
            console.print(f"[bold red]❌ Failed to generate a valid runbook after {max_attempts} attempts.[/bold red]")
            for v in schema_violations:
                console.print(f"  [red]• {v}[/red]")
            raise typer.Exit(code=1)
>>>
<<<SEARCH
    # 5.1 Schema validation — warn immediately so the developer can iterate
    schema_violations = validate_runbook_schema(content)
    if schema_violations:
        console.print(
            f"\n[bold yellow]⚠️  RUNBOOK SCHEMA WARNINGS ({len(schema_violations)}):[/bold yellow]"
        )
        for v in schema_violations:
            console.print(f"  [yellow]• {v}[/yellow]")
        console.print(
            "[dim]Fix the runbook before running 'agent implement'. "
            "The implement command will refuse to apply a schema-invalid runbook.[/dim]"
        )
    else:
        console.print("[dim]✅ Schema valid — all implementation blocks are correctly formatted.[/dim]")
===
    # 5.1 Schema validation status
    console.print("[dim]✅ Schema valid — all implementation blocks are correctly formatted.[/dim]")
>>>
```

### Step 3: Replace regex-based validate_runbook_schema with Pydantic-backed validator

Add a new import for the Pydantic models and `ValidationError` at the top of `parser.py`, then replace the entire `validate_runbook_schema` function with a Pydantic-based implementation that preserves the `List[str]` return contract.

#### [MODIFY] .agent/src/agent/core/implement/parser.py

```
<<<SEARCH
import re
from typing import Dict, List, Tuple
===
import re
from typing import Dict, List, Tuple, Union, Optional

from pydantic import ValidationError

from agent.core.implement.models import (
    RunbookSchema,
    RunbookStep,
    ModifyBlock,
    NewBlock,
    DeleteBlock,
    SearchReplaceBlock,
)
>>>
<<<SEARCH
def validate_runbook_schema(content: str) -> List[str]:
    """Validate a runbook's implementation block structure against the format contract.

    Checks every ``#### [MODIFY]``, ``#### [NEW]``, and ``#### [DELETE]``
    block in the Implementation Steps section and returns a list of human-readable
    violations. An empty list means the runbook is structurally valid.

    Rules enforced:

    - ``[MODIFY] <path>``: must have at least one ``<<<SEARCH`` block.
      A bare fenced code block without ``<<<SEARCH`` is a contract violation.
    - ``[NEW] <path>``: must have a fenced code block. A ``<<<SEARCH``
      block without any code fence means the file content is missing.
      (Note: ``[NEW]`` + ``<<<SEARCH`` inside a fence is valid for idempotency
      and is handled by the S/R parser — it is not flagged here.)
    - ``[DELETE] <path>``: must have a non-empty body (rationale required).
    - The runbook must contain an ``## Implementation Steps`` section.

    Args:
        content: Full runbook markdown text.

    Returns:
        List of violation strings. Empty list means schema is valid.
    """
    violations: List[str] = []

    # Rule 0: must have an implementation section
    if not re.search(r'^##\s+Implementation Steps', content, re.MULTILINE):
        violations.append(
            "Missing '## Implementation Steps' section — runbook has no executable steps."
        )
        return violations  # No point checking individual blocks without the section

    # Locate the implementation steps body
    impl_match = re.search(
        r'## Implementation Steps\s*(.*?)(?=^## |\Z)', content,
        re.DOTALL | re.MULTILINE,
    )
    body = impl_match.group(1) if impl_match else ""

    # Split into individual action blocks: #### [ACTION] <path>
    block_pattern = re.compile(
        r'####\s*\[(MODIFY|NEW|DELETE)\]\s*`?([^\n`]+?)`?\s*\n',
        re.IGNORECASE,
    )
    block_matches = list(block_pattern.finditer(body))

    for idx, match in enumerate(block_matches):
        action = match.group(1).upper()
        filepath = match.group(2).strip()
        # Block body is everything between this header and the next header (or end)
        start = match.end()
        end = block_matches[idx + 1].start() if idx + 1 < len(block_matches) else len(body)
        block_body = body[start:end]

        if action == "MODIFY":
            has_sr = bool(re.search(r'<<<SEARCH', block_body))
            if not has_sr:
                violations.append(
                    f"[MODIFY] '{filepath}': missing <<<SEARCH/===/>>> block. "
                    f"[MODIFY] must use search/replace, never a full code block."
                )

        elif action == "NEW":
            has_fence = bool(re.search(r'```[\w]*\n', block_body))
            if not has_fence:
                violations.append(
                    f"[NEW] '{filepath}': missing fenced code block. "
                    f"[NEW] must provide complete file content in a fenced block."
                )

        elif action == "DELETE":
            stripped = block_body.strip()
            if not stripped:
                violations.append(
                    f"[DELETE] '{filepath}': missing rationale. "
                    f"Add a one-line comment explaining why this file is removed."
                )

    return violations
===
def _extract_runbook_data(content: str) -> List[dict]:
    """Extract implementation steps from runbook markdown into Pydantic-ready dicts.

    Parses ``## Implementation Steps`` to find ``### Step N`` headers,
    then within each step finds ``#### [MODIFY|NEW|DELETE]`` blocks and
    extracts their content into structured dictionaries.

    Args:
        content: Full runbook markdown text.

    Returns:
        List of step dicts suitable for ``RunbookSchema(steps=...)``.

    Raises:
        ValueError: If the ``## Implementation Steps`` section is missing.
    """
    if not re.search(r'^##\s+Implementation Steps', content, re.MULTILINE):
        raise ValueError(
            "Missing '## Implementation Steps' section — runbook has no executable steps."
        )

    impl_match = re.search(
        r'## Implementation Steps\s*(.*?)(?=^## |\Z)', content,
        re.DOTALL | re.MULTILINE,
    )
    body = impl_match.group(1) if impl_match else ""

    # Split into steps by ### headers
    step_splits = re.split(r'\n### ', body)
    steps: List[dict] = []

    for raw_step in step_splits[1:]:  # skip preamble before first ###
        title_match = re.match(r'(?:Step\s+\d+:\s*)?(.+)', raw_step.splitlines()[0])
        title = title_match.group(1).strip() if title_match else "Untitled Step"

        block_pattern = re.compile(
            r'####\s*\[(MODIFY|NEW|DELETE)\]\s*`?([^\n`]+?)`?\s*\n',
            re.IGNORECASE,
        )
        block_matches = list(block_pattern.finditer(raw_step))
        operations: List[dict] = []

        for idx, match in enumerate(block_matches):
            action = match.group(1).upper()
            filepath = match.group(2).strip()
            start = match.end()
            end = block_matches[idx + 1].start() if idx + 1 < len(block_matches) else len(raw_step)
            block_body = raw_step[start:end]

            if action == "MODIFY":
                sr_blocks = []
                for sr in re.finditer(r'<<<SEARCH\n(.*?)\n===\n(.*?)\n>>>', block_body, re.DOTALL):
                    sr_blocks.append({"search": sr.group(1), "replace": sr.group(2)})
                operations.append({"path": filepath, "blocks": sr_blocks})

            elif action == "NEW":
                fence_match = re.search(r'```[\w]*\n(.*?)```', block_body, re.DOTALL)
                file_content = fence_match.group(1).rstrip() if fence_match else ""
                operations.append({"path": filepath, "content": file_content})

            elif action == "DELETE":
                rationale = block_body.strip()
                # Strip HTML comments
                rationale = re.sub(r'<!--\s*|\s*-->', '', rationale).strip()
                operations.append({"path": filepath, "rationale": rationale or ""})

        if operations:
            steps.append({"title": title, "operations": operations})

    return steps


def validate_runbook_schema(content: str) -> List[str]:
    """Validate a runbook's implementation block structure using Pydantic models.

    Extracts the ``## Implementation Steps`` section, parses it into
    structured dictionaries, and validates against :class:`RunbookSchema`.
    Returns a list of human-readable violations preserving the ``List[str]``
    contract expected by callers.

    Args:
        content: Full runbook markdown text.

    Returns:
        List of violation strings. Empty list means schema is valid.
    """
    violations: List[str] = []

    try:
        step_data = _extract_runbook_data(content)
        RunbookSchema(steps=step_data)
    except ValidationError as exc:
        for error in exc.errors():
            loc = " -> ".join(str(item) for item in error["loc"])
            violations.append(f"[{loc}]: {error['msg']}")
    except ValueError as exc:
        violations.append(str(exc))
    except Exception as exc:
        violations.append(f"Structural error: {exc}")

    return violations
>>>
```

## Verification Plan

### Automated Tests

- [ ] `pytest .agent/tests/test_parser.py`: Verify that the new Pydantic-based validator correctly rejects empty search blocks.
- [ ] `pytest .agent/tests/test_runbook.py`: Verify the self-correction loop by mocking a failed first attempt followed by a successful second attempt.
- [ ] `agent new-runbook INFRA-134 --skip-forecast`: Run the command on this story to ensure it generates and validates correctly.

### Manual Verification

- [ ] Deliberately introduce an empty `<<<SEARCH` block into a generated runbook and verify that `agent implement` rejects it with a clear error message.
- [ ] Verify that a `COMMITTED` story triggers the generation workflow correctly.

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated with INFRA-134.
- [ ] `agent/core/implement/models.py` contains PEP-257 docstrings for all models.

### Observability

- [ ] Logs show `runbook_validation_fail` with structured error counts.
- [ ] Telemetry traces include validation latency.

### Testing

- [ ] All existing parser tests pass.
- [ ] New unit tests added for `RunbookSchema` in `models.py`.

## Copyright

Copyright 2026 Justin Cook
