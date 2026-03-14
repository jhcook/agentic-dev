# INFRA-129: Icebox Features for Future Addon

## State
PROPOSED

## Related Story
INFRA-130, INFRA-131, INFRA-132

## Summary
With the recent branch switch to `main`, we inherited several over-scoped features (Local Web Platform, PM Persona, Console/Voice unification). Instead of deleting this good work, we are moving these features to an `ICEBOX` state. This removes them from the active core agentic context (adhering to our "Rule Diet") while preserving the code and stories so they can be extracted into separate addons/plugins in the future.

## Objectives
- **Preserve Good Work**: Put these stories and journeys into an `ICEBOX` state rather than simply deprecating them, so they can be resurrected as separate plugins.
- **Context Window Protection**: Ensure these iceboxed features do not bloat the core agentic context.

## Milestones
- **M1: Icebox the Local Web Platform (WEB)** (INFRA-130)
- **M2: Icebox the Project Manager Persona (MISC)** (INFRA-131)
- **M3: Icebox Voice and Console Interface Unification (INFRA)** (INFRA-132)

## Risks & Mitigations
- **Risk**: Losing track of iceboxed features.
  - **Mitigation**: They are explicitly tagged as ICEBOX so they can be found when we are ready to build the addon system.

## Verification
- Run `ls -R .agent/cache/stories` and verify that the TARGETED files are marked as `ICEBOX`.
- Ensure no `.agent/src/` code is accidentally deleted during this documentation cleanup.
- Confirm `git diff` shows only state metadata changes in `cache/stories` and `cache/journeys`.

## Copyright

Copyright 2026 Justin Cook
