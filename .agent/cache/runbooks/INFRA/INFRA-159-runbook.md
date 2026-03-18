# STORY-ID: INFRA-159: Validate S/R Search Blocks Against Actual File Content at Runbook Generation Time

## State

ACCEPTED

## Goal Description

Implement a validation pass in `agent new-runbook` that verifies every `<<<SEARCH` block in a generated runbook draft against the actual file content on disk. This prevents "hallucinated" search targets from reaching the developer, ensuring that `agent implement` never fails due to search-mismatch errors. The system will automatically attempt to correct mismatches using the AI panel (up to 2 retries) by providing the AI with the verbatim file content.

## Linked Journeys

- None

## Panel Review Findings

### @Architect
- Validation pass follows the "Self-Healing" pattern established in INFRA-155.
- Logic is placed in `commands/utils.py` to keep `runbook.py` focused on the command workflow.
- Respects architectural boundaries by reusing `core.implement` concepts for path resolution.

### @Qa
- Test strategy covers success, mismatch retries, exhausted retries, and missing target files.
- Verbatim matching logic includes trailing whitespace normalization per line to improve robustness against minor AI formatting variance.

### @Security
- NFR compliance: File contents used for verification are never logged at INFO level or above.
- Retains existing `scrub_sensitive_data` pattern for AI interactions.

### @Product
- Acceptance criteria (AC-1 to AC-7) are fully addressed.
- The "Hard block" (AC-2) ensures zero-defect runbooks are saved to disk.

### @Observability
- New structured log events (`sr_validation_pass`, `sr_validation_fail`, etc.) provide visibility into AI hallucination rates and self-healing success.

### @Docs
- CHANGELOG.md will be updated to reflect the new safety check.

### @Compliance
- No PII handling changes. Logic is pure code validation.

### @Backend
- strictly typed Python functions and docstrings for all new utility methods.
- Correct use of repo-relative path resolution ensures consistency with the implementation pipeline.

## Codebase Introspection

### Targeted File Contents (from source)

- `.agent/src/agent/commands/runbook.py`: Contains the `new_runbook` command and the AI generation loop.
- `.agent/src/agent/commands/utils.py`: Contains shared command utilities.

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| `.agent/tests/commands/test_runbook.py` | | | Add integration tests for S/R validation loop |
| `.agent/tests/commands/test_commands_utils.py` | | | Add unit tests for `validate_sr_blocks` |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| Generation attempts | `runbook.py` | `max_attempts = 3` | Yes |
| Runbook save path | `runbook.py` | `.agent/runbooks/<SCOPE>/<ID>-runbook.md` | Yes |
| State Requirement | `runbook.py` | `COMMITTED` | Yes |

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Consolidate implementation Operation header regex between `parser.py` and `utils.py` if possible (logic is duplicated for validation performance).

## Implementation Steps

### Step 1: Add S/R validation utilities to `agent/commands/utils.py`

#### [MODIFY] .agent/src/agent/commands/utils.py

```
<<<SEARCH
def scrub_sensitive_data(text: str) -> str:
    """
    Scrub sensitive data (PII, Secrets) from text using regex patterns.
===
def _lines_match(search_text: str, file_text: str) -> bool:
    """Verifies if search_text exists in file_text, ignoring trailing whitespace per line.

    Args:
        search_text: The block of text to search for.
        file_text: The content of the file to search in.

    Returns:
        True if the search_text (normalized) exists as a contiguous block in file_text.
    """
    search_lines = [line.rstrip() for line in search_text.splitlines()]
    file_lines = [line.rstrip() for line in file_text.splitlines()]

    if not search_lines:
        return True

    for i in range(len(file_lines) - len(search_lines) + 1):
        if file_lines[i : i + len(search_lines)] == search_lines:
            return True
    return False


def validate_sr_blocks(content: str) -> List[dict]:
    """Validate SEARCH blocks in a runbook against actual files on disk.

    Args:
        content: The runbook markdown content.

    Returns:
        List of dictionaries containing mismatch details:
        {'file': str, 'search': str, 'actual': str, 'index': int}

    Raises:
        FileNotFoundError: If a [MODIFY] block targets a missing file.
    """
    from agent.core.implement.resolver import resolve_path

    mismatches = []
    # Pattern captures the operation type, the file path, and the body until next operation or header
    pattern = r'####\s*\[(MODIFY|NEW)\]\s*`?([^\n`]+?)`?\s*\n(.*?)(?=\n####\s*\[|\Z)'

    for match in re.finditer(pattern, content, re.DOTALL | re.IGNORECASE):
        op_type = match.group(1).upper()
        file_path_str = match.group(2).strip()
        body = match.group(3)

        try:
            abs_path = resolve_path(file_path_str)
        except (ValueError, FileNotFoundError):
            abs_path = None

        if op_type == "MODIFY":
            if not abs_path or not abs_path.exists():
                raise FileNotFoundError(f"Target file for [MODIFY] does not exist: {file_path_str}")

        # Exempt NEW if file doesn't exist
        if op_type == "NEW" and (not abs_path or not abs_path.exists()):
            continue

        if abs_path and abs_path.exists():
            file_text = abs_path.read_text()
            # Find all SEARCH blocks in the body
            sr_pattern = r'<<<SEARCH\n(.*?)\n===\n(.*?)\n>>>'
            block_idx = 0
            for sr_match in re.finditer(sr_pattern, body, re.DOTALL):
                block_idx += 1
                search_text = sr_match.group(1)
                if not _lines_match(search_text, file_text):
                    mismatches.append({
                        "file": file_path_str,
                        "search": search_text,
                        "actual": file_text,
                        "index": block_idx,
                    })

    return mismatches


def generate_sr_correction_prompt(mismatches: List[dict]) -> str:
    """Generate an AI correction prompt for failing S/R blocks.

    Args:
        mismatches: List of mismatch details from validate_sr_blocks.

    Returns:
        Formatted instruction string for the AI.
    """
    msg = "S/R VALIDATION FAILED. The following SEARCH blocks do not match the target files:\n\n"
    for m in mismatches:
        msg += f"FILE: {m['file']} (Block #{m['index']})\n"
        msg += f"FAILING SEARCH BLOCK:\n{m['search']}\n\n"
        msg += f"ACTUAL FILE CONTENT FOR {m['file']}:\n{m['actual']}\n"
        msg += "---\n"
    msg += (
        "\nInstruction: Rewrite the implementation steps above so that EVERY <<<SEARCH block "
        "exactly matches the actual file content provided. Use the provided actual content "
        "to ensure verbatim matching. Return the FULL updated runbook."
    )
    return msg


def scrub_sensitive_data(text: str) -> str:
    """
    Scrub sensitive data (PII, Secrets) from text using regex patterns.
>>>
```

### Step 2: Integrate validation pass into `new_runbook` loop

#### [MODIFY] .agent/src/agent/commands/runbook.py

```
<<<SEARCH
from agent.commands.utils import (
    extract_adr_refs,
    extract_journey_refs,
    merge_story_links,
)
===
from agent.commands.utils import (
    extract_adr_refs,
    extract_journey_refs,
    merge_story_links,
    validate_sr_blocks,
    generate_sr_correction_prompt,
)
>>>
```

```
<<<SEARCH
        if code_errors:
            logger.warning("runbook_code_gate_fail", extra={"attempt": attempt, "story_id": story_id, "errors": code_errors})
            error_msg = "CODE GATE VIOLATIONS DETECTED:\n" + "\n".join(f"- {e}" for e in code_errors)
            if attempt < max_attempts:
                console.print(f"[yellow]⚠️  Attempt {attempt} failed code gates. Asking AI for self-healing...[/yellow]")
                current_user_prompt = f"{user_prompt}\n\n{error_msg}\nPlease fix these code violations and re-generate the full runbook."
                continue
            else:
                error_console.print(f"[bold red]❌ Code gates failed after {max_attempts} attempts.[/bold red]")
                error_console.print(error_msg)
                raise typer.Exit(code=1)
        
        # If we got here, schema and code errors are clear
===
        if code_errors:
            logger.warning("runbook_code_gate_fail", extra={"attempt": attempt, "story_id": story_id, "errors": code_errors})
            error_msg = "CODE GATE VIOLATIONS DETECTED:\n" + "\n".join(f"- {e}" for e in code_errors)
            if attempt < max_attempts:
                console.print(f"[yellow]⚠️  Attempt {attempt} failed code gates. Asking AI for self-healing...[/yellow]")
                current_user_prompt = f"{user_prompt}\n\n{error_msg}\nPlease fix these code violations and re-generate the full runbook."
                continue
            else:
                error_console.print(f"[bold red]❌ Code gates failed after {max_attempts} attempts.[/bold red]")
                error_console.print(error_msg)
                raise typer.Exit(code=1)

        # 3. S/R Validation (INFRA-159)
        try:
            sr_mismatches = validate_sr_blocks(content)
        except FileNotFoundError as exc:
            # AC-6: Missing target file in MODIFY block is an immediate failure (no retry)
            error_console.print(f"[bold red]❌ S/R Validation Error: {exc}[/bold red]")
            raise typer.Exit(code=1)

        if sr_mismatches:
            # AC-7: Log failure
            logger.warning(
                "sr_validation_fail",
                extra={
                    "attempt": attempt,
                    "story_id": story_id,
                    "count": len(sr_mismatches),
                    "files": [m["file"] for m in sr_mismatches]
                }
            )

            if attempt < max_attempts:
                console.print(f"[yellow]⚠️  Attempt {attempt} failed S/R validation ({len(sr_mismatches)} mismatch). Retrying...[/yellow]")
                sr_error_msg = generate_sr_correction_prompt(sr_mismatches)
                current_user_prompt = f"{user_prompt}\n\n{sr_error_msg}"
                logger.info("sr_correction_attempt", extra={"attempt": attempt, "story_id": story_id})
                continue
            else:
                # AC-4: Exhausted retries
                logger.error("sr_correction_exhausted", extra={"story_id": story_id})
                error_console.print(f"[bold red]❌ S/R validation failed after {max_attempts} attempts.[/bold red]")
                for m in sr_mismatches:
                    error_console.print(f"  [red]• File: {m['file']} (Block #{m['index']})[/red]")
                raise typer.Exit(code=1)
        else:
            if attempt > 1:
                logger.info("sr_correction_success", extra={"story_id": story_id, "attempt": attempt})
            logger.info("sr_validation_pass", extra={"story_id": story_id})
        
        # If we got here, all validations passed
>>>
```

## Verification Plan

### Automated Tests

- [ ] **Unit tests in `tests/commands/test_commands_utils.py`**:
  - Test `_lines_match` with various whitespace scenarios.
  - Test `validate_sr_blocks` with valid search, mismatched search, missing file (expect `FileNotFoundError`), and `[NEW]` file exemption.
- [ ] **Integration tests in `tests/commands/test_runbook.py`**:
  - Mock AI to return a mismatched SEARCH block on first call and correct content on second; verify runbook is saved correctly.
  - Mock AI to consistently return bad SEARCH blocks; verify exit code `1` after 2 retries.

### Manual Verification

- [ ] Run `agent new-runbook <ID>` on a story known to touch complex files (like `runbook.py`). Verify in the console output that "S/R validation passed" or a retry occurred.
- [ ] Artificially modify a generated runbook draft to include a `[MODIFY]` block for a non-existent file and run a script that simulates the validation logic (or trigger generation again if idempotent).

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated with INFRA-159 S/R pre-validation details.

### Observability

- [ ] Logs are structured and include `sr_validation_pass`, `sr_validation_fail`, `sr_correction_attempt`, `sr_correction_success`, `sr_correction_exhausted`.
- [ ] File contents are excluded from all INFO and above level logs.

### Testing

- [ ] All existing tests pass.
- [ ] New unit and integration tests added.

## Copyright

Copyright 2026 Justin Cook
