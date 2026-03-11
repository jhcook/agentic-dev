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

(Agent: Copy actual function/class signatures from TARGETED FILE CONTENTS context. Do NOT invent signatures.)

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| (Agent: Populate from TEST IMPACT MATRIX context) | | | |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| (Agent: Populate from BEHAVIORAL CONTRACTS context) | | | |

## Targeted Refactors & Cleanups (INFRA-043)

(Agent: List tech debt or "cleanup" items here. User: Check [x] to approve implementation.)

- [ ] < Example cleanup item >

## Implementation Steps

> **Steps must be machine-executable.** Every step must use exactly one of the three
> action markers below, followed by concrete content the CLI can apply verbatim.
> Do NOT write prose instructions — the tool applies these literally.
>
> - **`#### [MODIFY] <path>`** — change an existing file.
>   Follow with one or more `<<<SEARCH / === / >>>` blocks. The SEARCH text must be
>   copied verbatim from the current file (use the Codebase Introspection section above).
>
> - **`#### [NEW] <path>`** — create a new file.
>   Follow with the complete file content in a fenced code block. No placeholders.
>
> - **`#### [DELETE] <path>`** — remove a file.
>   Follow with a one-line rationale comment. No code block needed.
>
> Use the **full repo-relative path** from the repo root for every `<path>`.
> One logical concern per `### Step N` — split if in doubt.

### Step 1: < Descriptive title — what changes and why >

#### [MODIFY] < path/to/existing/file >

```
<<<SEARCH
< exact lines from the current file >
===
< replacement lines >
>>>
```

### Step 2: < Create a new file >

#### [NEW] < path/to/new/file >

```
< complete file content >
```

### Step 3: < Remove an obsolete file >

#### [DELETE] < path/to/obsolete/file >

<!-- < one-line rationale > -->

## Verification Plan

### Automated Tests

- [ ] < Test command and expected outcome >

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
- [ ] New tests added for each new public interface

## Copyright

{{ COPYRIGHT_HEADER }}
