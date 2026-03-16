# STORY-ID: INFRA-149: Schema Validation CLI Gate

## State

ACCEPTED

## Goal Description

The objective is to implement a strict validation gate within the CLI to ensure that AI-generated runbooks adhere to the standardized schema before they are written to disk or applied to the workspace. This prevents structurally invalid artifacts from entering the pipeline, providing immediate feedback to the developer and improving the reliability of the automated implementation workflow.

## Linked Journeys

- JRN-003: Automated Runbook Generation
- JRN-007: Manual Runbook Application

## Panel Review Findings

### @Architect
- **Verdict**: APPROVE
- **Summary**: The addition of a validation gate at the boundary of file I/O is a sound architectural improvement that enforces ADR-014 (Standardized Runbook Schema) earlier in the lifecycle.
- **Findings**:
  - The plan correctly targets both the creation (`new-runbook`) and update (`panel --apply`) paths.
  - Using a centralized utility for error formatting ensures consistency across different commands.

### @Qa
- **Verdict**: APPROVE
- **Summary**: Immediate feedback on schema errors will significantly reduce debugging time during implementation.
- **Findings**:
  - The implementation includes a "Validation Error Formatter" which is critical for making Pydantic errors actionable for users.
  - Exit codes (non-zero for failures) are correctly specified to support CI/CD integration.

### @Security
- **Verdict**: APPROVE
- **Summary**: Validation logic is kept local, and existing PII scrubbing patterns are maintained.
- **Findings**:
  - The `scrub_sensitive_data` utility is already utilized in the target files and will continue to be used for the content being validated.

### @Product
- **Verdict**: APPROVE
- **Summary**: This solves a key pain point where invalid runbooks would silently fail later in the `implement` phase.
- **Findings**:
  - Acceptance criteria are well-defined and covered by the implementation plan.

### @Observability
- **Verdict**: APPROVE
- **Summary**: Validation failures will be logged to `stderr` and the internal logger for traceability.
- **Findings**:
  - The existing `logger.warning` in `runbook.py` already captures validation metadata; this implementation extends that pattern.

### @Docs
- **Verdict**: APPROVE
- **Summary**: Documentation for the new CLI behavior will be added to the CHANGELOG.
- **Findings**:
  - N/A.

### @Compliance
- **Verdict**: APPROVE
- **Summary**: No changes to data handling or lawful basis; purely a structural integrity check for internal tooling.
- **Findings**:
  - N/A.

### @Backend
- **Verdict**: APPROVE
- **Summary**: Proper Pydantic integration and strict typing for the new utility.
- **Findings**:
  - Ensure `format_runbook_errors` handles the Pydantic `ErrorDict` structure correctly.

## Codebase Introspection

### Targeted File Contents (from source)

(Targeted file contents for `agent/commands/panel.py` and `agent/commands/runbook.py` are provided in the prompt context.)

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| `.agent/tests/commands/test_panel.py` | `agent.commands.panel.convene_council_full` | `agent.commands.panel.validate_runbook_schema` | Verify validation gate in `--apply` |
| `.agent/tests/commands/test_runbook.py` | `agent.commands.runbook.validate_runbook_schema` | `agent.utils.validation_formatter.format_runbook_errors` | Verify improved error output |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| Exit Code 1 on Story Missing | `panel.py` | 1 | Yes |
| Exit Code 2 on Complexity Over | `runbook.py` | 2 | Yes |
| Consultative Mode | `panel.py` | consultative | Yes |

## Targeted Refactors & Cleanups (INFRA-043)

- [x] Standardize imports in `runbook.py` to group core and utility imports cleanly.

## Implementation Steps

### Step 1: Create Validation Error Formatter

#### [NEW] .agent/src/agent/utils/validation_formatter.py

```python
"""
Formatting utilities for Pydantic validation errors in runbooks.
"""

from typing import Any, Dict, List, Union

def format_runbook_errors(errors: List[Union[str, Dict[str, Any]]]) -> str:
    """
    Format a list of validation errors into a human-readable string.

    Handles both raw strings and Pydantic-style error dictionaries.

    Args:
        errors: A list of error messages or Pydantic error dictionaries.

    Returns:
        A formatted markdown string for CLI display.
    """
    if not errors:
        return ""

    lines = ["### SCHEMA VALIDATION FAILED ###"]
    
    for i, err in enumerate(errors, 1):
        if isinstance(err, str):
            lines.append(f"{i}. {err}")
        elif isinstance(err, dict):
            # Handle Pydantic ErrorDict (loc, msg, type)
            loc = " -> ".join(str(p) for p in err.get("loc", []))
            msg = err.get("msg", "Unknown error")
            
            # Identify step index for implementation blocks
            step_marker = ""
            if "steps" in err.get("loc", []):
                for p in err.get("loc", []):
                    if isinstance(p, int):
                        step_marker = f" (Step {p + 1})"
                        break
            
            lines.append(f"{i}. [bold red]{loc}[/bold red]{step_marker}: {msg}")
        else:
            lines.append(f"{i}. {str(err)}")
            
    return "\n".join(lines)
```

### Step 2: Integrate Validation Gate in `new-runbook`

#### [MODIFY] .agent/src/agent/commands/runbook.py

```
<<<SEARCH
from agent.core.context import context_loader
from agent.core.implement.orchestrator import validate_runbook_schema
from agent.db.client import upsert_artifact
===
from agent.core.context import context_loader
from agent.core.implement.orchestrator import validate_runbook_schema
from agent.utils.validation_formatter import format_runbook_errors
from agent.db.client import upsert_artifact
>>>
<<<SEARCH
        # Schema validation (AC-3)
        schema_violations = validate_runbook_schema(content)
        if not schema_violations:
            break
            
        logger.warning(
            "runbook_validation_fail",
            extra={
                "attempt": attempt,
                "story_id": story_id,
                "error_count": len(schema_violations),
                "validation_error": schema_violations,
            },
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
===
        # Schema validation (AC-3)
        schema_violations = validate_runbook_schema(content)
        if not schema_violations:
            break
            
        logger.warning(
            "runbook_validation_fail",
            extra={
                "attempt": attempt,
                "story_id": story_id,
                "error_count": len(schema_violations),
                "validation_error": schema_violations,
            },
        )
        
        formatted_errors = format_runbook_errors(schema_violations)
        
        if attempt < max_attempts:
            console.print(f"[yellow]⚠️  Attempt {attempt} failed validation. Asking for correction...[/yellow]")
            current_user_prompt = (
                f"{user_prompt}\n\n"
                f"{formatted_errors}\n\n"
                f"Please correct these errors and generate the full runbook again."
            )
        else:
            console.print(f"[bold red]❌ Failed to generate a valid runbook after {max_attempts} attempts.[/bold red]")
            console.print(formatted_errors)
            raise typer.Exit(code=1)
>>>
```

### Step 3: Integrate Validation Gate in Panel Apply

#### [MODIFY] .agent/src/agent/commands/panel.py

```
<<<SEARCH
from agent.core.check.reporting import print_reference_summary as _print_reference_summary
from agent.core.context import context_loader

console = Console()
===
from agent.core.check.reporting import print_reference_summary as _print_reference_summary
from agent.core.context import context_loader
from agent.core.implement.orchestrator import validate_runbook_schema
from agent.utils.validation_formatter import format_runbook_errors

console = Console()
>>>
<<<SEARCH
        # Safety check: ensure content is not empty
        if updated_content and len(updated_content) > 100:
            target_file.write_text(updated_content)
            console.print(f"[bold green]✅ Applied advice to {target_file.name}[/bold green]")
        else:
             console.print("[bold red]❌ Failed to generate valid update (Content empty or too short).[/bold red]")
===
        # Safety check: ensure content is not empty
        if updated_content and len(updated_content) > 100:
            # INFRA-149: Schema validation for runbooks before applying
            if "runbook" in target_file.name.lower():
                violations = validate_runbook_schema(updated_content)
                if violations:
                    console.print(f"[bold red]❌ Validation failed for {target_file.name}:[/bold red]")
                    console.print(format_runbook_errors(violations))
                    console.print("[yellow]Aborting apply to prevent file corruption.[/yellow]")
                    raise typer.Exit(code=1)
            
            target_file.write_text(updated_content)
            console.print(f"[bold green]✅ Applied advice to {target_file.name}[/bold green]")
        else:
             console.print("[bold red]❌ Failed to generate valid update (Content empty or too short).[/bold red]")
>>>
```

## Verification Plan

### Automated Tests

- [ ] `pytest .agent/tests/commands/test_runbook.py` - Verify `new-runbook` retries on validation failure and exits on final failure.
- [ ] `pytest .agent/tests/commands/test_panel.py` - Verify `agent panel --apply` blocks writes for invalid runbooks.
- [ ] Create a new unit test for `agent.utils.validation_formatter.format_runbook_errors` verifying handling of both strings and dicts.

### Manual Verification

- [ ] Run `agent new-runbook INFRA-149` with a mock provider that returns a runbook missing `<<<SEARCH` blocks. Expected: CLI displays formatted errors and retries.
- [ ] Run `agent panel INFRA-149 --apply` on a runbook and ensure that if the AI response is malformed, the file is NOT updated and a red error is shown.

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated with INFRA-149: Schema Validation CLI Gate.

### Observability

- [ ] Logs are structured and free of PII.
- [ ] New structured `extra=` dicts added if new logging added (using existing warning logs).

### Testing

- [ ] All existing tests pass.
- [ ] New tests added for the validation formatter.

## Copyright

Copyright 2026 Justin Cook
