# STORY-ID: < Title >

## State

PROPOSED

## Goal Description

< Clear one-paragraph summary of the objective and WHY it is needed >

## Linked Journeys

- JRN-XXX: < Journey title >

## Panel Review Findings

(Critique the story/plan from each perspective)
{panel_checks}

## Codebase Introspection

### Target File Signatures (from source)

(Agent: Copy actual function/class signatures from TARGETED FILE SIGNATURES context. Do NOT invent signatures.)

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|--------------------|
| (Agent: Populate from TEST IMPACT MATRIX context) | | | |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| (Agent: Populate from BEHAVIORAL CONTRACTS context) | | | |

## Targeted Refactors & Cleanups (INFRA-043)

(Agent: List tech debt or "cleanup" items here. User: Check [x] to approve implementation.)

- [ ] Example: Convert prints to logger in `src/utils.py`

## Implementation Steps

> **MACHINE-EXECUTABLE FORMAT RULES — Do NOT write prose; the CLI applies these literally.**
>
> **Rule 1 — Modifying an existing file:** Use `#### [MODIFY] path/to/file.py` followed by
> one or more exact `<<<SEARCH/===/>>>` blocks. The SEARCH text must be a verbatim excerpt
> from the current file (copy it from the Codebase Introspection section above).
>
> **Rule 2 — Creating a new file:** Use `#### [NEW] path/to/file.py` followed by the
> complete file content in a fenced code block. No placeholders; the block is written verbatim.
>
> **Rule 3 — Deleting a file:** Use `#### [DELETE] path/to/file.py` with a one-line
> rationale comment. No code block needed.
>
> **Rule 4 — Absolute paths only.** Use the full repo-relative path from the repo root,
> e.g. `.agent/src/agent/core/ai/providers/openai.py`, not `src/agent/…`.
>
> **Rule 5 — One concern per step.** Each `### Step N` heading must touch ≤ 1 logical unit
> (one class, one function, one config key). Split if in doubt.

### Step 1: < Descriptive title — what changes and why >

#### [MODIFY] .agent/src/agent/core/example.py

```
<<<SEARCH
def old_function():
    pass
===
def old_function():
    """Docstring."""
    return "updated"
>>>
```

### Step 2: < Create new file >

#### [NEW] .agent/src/agent/core/ai/providers/example.py

```python
# Copyright 2026 Justin Cook
# Licensed under the Apache License, Version 2.0
"""Module docstring."""

class ExampleProvider:
    """Example."""
    ...
```

### Step 3: < Delete obsolete file >

#### [DELETE] .agent/src/agent/core/ai/old_module.py

<!-- Replaced by providers/ package in Step 2. -->

## Verification Plan

### Automated Tests

- [ ] `pytest .agent/src/agent/core/ai/tests/ -v` — all AI tests pass
- [ ] `python -c "import agent.cli"` — no circular imports

### Manual Verification

- [ ] < Concrete command to run and expected output >

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated
- [ ] README.md updated (if applicable)

### Observability

- [ ] Logs are structured and free of PII
- [ ] New structured `extra=` dicts added if new logging added

### Testing

- [ ] All existing tests pass
- [ ] New unit tests added for each new public class/function

## Copyright

{{ COPYRIGHT_HEADER }}
