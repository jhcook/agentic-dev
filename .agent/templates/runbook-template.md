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

### Targeted File Contents (from source)

(Agent: Use the full file content below to accurately construct <<<SEARCH blocks and copy relevant code. Do not invent code.)

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
> - **`#### [MODIFY] <path>`** — change an **existing** file.
>   Follow with one or more `<<<SEARCH / === / >>>` blocks. The SEARCH text must be
>   copied verbatim from the current file (use the Codebase Introspection section above).
>   ⚠️  NEVER follow `[MODIFY]` with a full fenced code block — only `<<<SEARCH` blocks.
>
> - **`#### [NEW] <path>`** — create a **brand-new** file that does not yet exist in the SOURCE FILE TREE.
>   Follow with the complete file content in a fenced code block. No placeholders.
>   ⚠️  If the file already exists in the repo (even if you are rewriting it completely), you MUST use `[MODIFY]`
>   with a `<<<SEARCH` block that matches the entire existing file contents.
>   ⚠️  Every module, class, and function MUST have a PEP-257 docstring — including
>   inner/closure functions. The docstring gate will reject files missing them.
>
> - **`#### [DELETE] <path>`** — remove a file.
>   Follow with a one-line rationale comment. No code block needed.
>
> Use the **full repo-relative path** from the repo root for every `<path>` (e.g., starting with `.agent/src/`, NOT just `src/`).
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
< complete file content — with any required license/copyright header, module-level doc, and all public interfaces >
```

### Step 2b: < Tests for Step 2 — MANDATORY >

> ⚠️  **MANDATORY — every `[NEW]` implementation file requires a paired test step.**
> Missing test files are machine-verified and will block acceptance. Do NOT skip.

#### [NEW] < path/to/tests/test_new_file >

```
< complete test file — covering every public function/class/method in Step 2, using the project's test framework >
```

### Step 3: < Remove an obsolete file >

#### [DELETE] < path/to/obsolete/file >

<!-- < one-line rationale > -->

### Step N-1: Update CHANGELOG.md

> ⚠️  **MANDATORY — do not skip.** Missing entries will be caught by `@docs` at preflight.

#### [MODIFY] CHANGELOG.md

```
<<<SEARCH
### Added
===
### Added
- **STORY-ID**: < one-sentence user-facing description of what changed and why it matters >
>>>
```

### Step N: Update Impact Analysis in story file

> ⚠️  **MANDATORY — do not skip.** Missing files will be caught by `@product` at preflight.

#### [MODIFY] .agent/cache/stories/< PREFIX >/< STORY-ID >-< slug >.md

```
<<<SEARCH
**Components touched:**
===
**Components touched:**
- `< every file created or modified >` — **[NEW|MODIFIED]** < one-line description >
>>>
```

## Verification Plan

### Automated Tests

- [ ] < Test command and expected outcome >

### Manual Verification

- [ ] < Concrete command to run and expected output >

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated (see Step N-1 above — this is a runbook step, not a suggestion)
- [ ] Story `## Impact Analysis Summary` updated to list every touched file (see Step N above)
- [ ] README.md updated (if applicable)

### Observability

- [ ] Logs are structured and free of PII
- [ ] New structured `extra=` dicts added if new logging added

### Testing

- [ ] All existing tests pass
- [ ] New tests added for each new public interface

## Copyright

{{ COPYRIGHT_HEADER }}
