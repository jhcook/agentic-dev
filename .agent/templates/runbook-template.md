# STORY-ID: < Title >

## State

PROPOSED

## Goal Description

< Clear summary of the objective >

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
|-----------|---------------------|-----------------|-----------------|
| (Agent: Populate from TEST IMPACT MATRIX context) | | | |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| (Agent: Populate from BEHAVIORAL CONTRACTS context) | | | |

## Targeted Refactors & Cleanups (INFRA-043)

(Agent: List tech debt or "cleanup" items here. User: Check [x] to approve implementation.)

- [ ] Example: Convert prints to logger in `src/utils.py`
- [ ] Example: Fix formatting in `src/main.py`

## Implementation Steps

(Must be detailed enough for a qualified engineer)

### [Component Name]

#### [MODIFY | NEW | DELETE] [file path]

- < Specific instruction on what to change >
- < Code snippets if necessary for clarity >

## Verification Plan

### Automated Tests

- [ ] Test 1

### Manual Verification

- [ ] Step 1

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated
- [ ] README.md updated (if applicable)
- [ ] API Documentation updated (if applicable)

### Observability

- [ ] Logs are structured and free of PII
- [ ] Metrics added for new features

### Testing

- [ ] Unit tests passed
- [ ] Integration tests passed

## Copyright

{{ COPYRIGHT_HEADER }}
