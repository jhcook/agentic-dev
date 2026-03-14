# STORY-ID: INFRA-131: Icebox PM Persona Layer

## State

PROPOSED

## Goal Description

The objective of this story is to officially move the Project Manager Persona Layer (`INFRA-128`) to the `ICEBOX` state. This decision stems from the need to prioritize structural simplicity and adhere to the "Rule Diet" initiative, as the PM persona layer introduces significant RBAC complexity that is not currently aligned with the core engineering governance focus of the platform. By icing this story, we preserve the architectural research for future plugin development while maintaining a leaner core framework.

## Linked Journeys

- None active.

## Panel Review Findings

### @Architect
The transition of INFRA-128 to ICEBOX is architecturally sound. It respects the boundaries defined in ADR-012 by acknowledging the separation of concerns but choosing not to implement the PM-specific layer at this stage to avoid RBAC bloat. This follows the principle of structural simplicity.

### @Qa
From a quality perspective, this is a documentation-only change in the story cache. No functional source code is touched. Verification will involve ensuring the Markdown files reflect the correct state and rationale, which can be verified via automated grep or file inspection.

### @Security
Reducing the scope of the RBAC system by icing the PM layer mitigates the risk of complex permission misconfigurations. This is a proactive security stance that favors the Principle of Least Privilege by not adding unnecessary roles.

### @Product
Icing this story correctly reflects the platform's current focus on engineering governance over broader project management features. It ensures the backlog remains relevant and that the team does not incur "complexity debt" for features that are not yet core to the value proposition.

### @Observability
No impact on system observability, as the change is limited to documentation in the `.agent/cache` directory.

### @Docs
The change explicitly updates the documentation state of the affected story. I have reviewed the rationale and it clearly explains why the story is being iced, which is essential for future developers revisiting this work.

### @Compliance
The story files retain their license and copyright headers. No PII or regulatory data is involved in this documentation update.

### @Mobile
No impact on the mobile application.

### @Web
No impact on the frontend codebase.

### @Backend
No impact on the FastAPI backend or RBAC middleware.

## Codebase Introspection

### Targeted File Contents (from source)

#### .agent/cache/stories/MISC/128-implement-project-manager-persona-layer.md
```markdown
# 128: Implement Project Manager Persona Layer

## State

ICEBOX 
*(Rationale: Preserved for future addon. The Project Manager Persona Layer adds RBAC complexity that dilutes the agent's focus on engineering governance, contradicting the Reliability Plan's goal of structural simplicity and "Rule Diet".)*

## Problem Statement
...
```

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| N/A | Documentation change | N/A | Verify file state via grep |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| Story State | INFRA-128 | ICEBOX | Yes |

## Targeted Refactors & Cleanups (INFRA-043)

- [x] Ensure rationale is consistently formatted across duplicated story cache entries.

## Implementation Steps

### Step 1: Update the state and rationale in the MISC cache

#### [MODIFY] .agent/cache/stories/MISC/128-implement-project-manager-persona-layer.md

```
<<<SEARCH
# 128: Implement Project Manager Persona Layer

## State

ICEBOX 
*(Rationale: Preserved for future addon. The Project Manager Persona Layer adds RBAC complexity that dilutes the agent's focus on engineering governance, contradicting the Reliability Plan's goal of structural simplicity and "Rule Diet".)*
===
# 128: Implement Project Manager Persona Layer

## State

ICEBOX 
*(Rationale: Preserved for future addon. The Project Manager Persona Layer adds RBAC complexity that dilutes the agent's focus on engineering governance, contradicting the Reliability Plan's goal of structural simplicity and "Rule Diet".)*
>>>
```

### Step 2: Update the state and rationale in the root story cache

#### [MODIFY] .agent/cache/stories/128-implement-project-manager-persona-layer.md

```
<<<SEARCH
# 128: Implement Project Manager Persona Layer

## State

ICEBOX 
*(Rationale: Preserved for future addon. The Project Manager Persona Layer adds RBAC complexity that dilutes the agent's focus on engineering governance, contradicting the Reliability Plan's goal of structural simplicity and "Rule Diet".)*
===
# 128: Implement Project Manager Persona Layer

## State

ICEBOX 
*(Rationale: Preserved for future addon. The Project Manager Persona Layer adds RBAC complexity that dilutes the agent's focus on engineering governance, contradicting the Reliability Plan's goal of structural simplicity and "Rule Diet".)*
>>>
```

## Verification Plan

### Automated Tests

- [ ] Run `grep -r "State: ICEBOX" .agent/cache/stories/` to ensure the state is correctly set.
- [ ] Run `grep -r "Rationale: Preserved for future addon" .agent/cache/stories/` to verify the rationale presence.

### Manual Verification

- [ ] Inspect the files `.agent/cache/stories/MISC/128-implement-project-manager-persona-layer.md` and `.agent/cache/stories/128-implement-project-manager-persona-layer.md` to ensure no accidental deletions of other sections.

## Definition of Done

### Documentation

- [x] CHANGELOG.md updated (N/A for doc-only maintenance)
- [x] README.md updated (N/A)

### Observability

- [x] Logs are structured and free of PII (N/A)
- [x] New structured `extra=` dicts added if new logging added (N/A)

### Testing

- [x] All existing tests pass
- [x] New tests added for each new public interface (N/A)

## Copyright

Copyright 2026 Justin Cook