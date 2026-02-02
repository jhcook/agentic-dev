# ADR-019: Global Artifact ID Strategy

## Status

ACCEPTED

## Context

As the Agentic Development system evolves, we have multiple artifact types (Plans, Stories, Runbooks, and ADRs). Originally, IDs were assigned loosely or per-type, leading to ambiguity (e.g., "Does 048 refer to the Plan or the Story?"). We need a consistent strategy to ensure unique addressability and clear relationships.

## Decision

We will adopt a **Global Unique ID Strategy** for all artifacts.

1. **Uniqueness**: IDs are NOT reused across artifact types.
    - If `INFRA-048` is a Plan, there shall be no `INFRA-048` Story.
2. **Exception (1:1 Relationships)**:
    - **Runbooks** are strictly 1:1 with **Stories**.
    - Therefore, a Runbook **MUST** share the ID of its parent Story.
    - `INFRA-060` (Story) <-> `INFRA-060` (Runbook).

## Consequences

- **Positive**:
  - Removes ambiguity in communication ("Look at 048" can only mean one high-level thing).
  - Simplifies mental model of the "Graph".
- **Negative**:
  - Gaps in IDs when listing just one type (e.g., `ls stories/` might show 048, 050, 052 because 049 is a Plan).
  - Requires strict discipline/tooling to assign the "Next Global ID".

## Implementation

- **Next ID Determination**:
    1. **Registry Sync (Preferred)**: If Supabase is configured (`agent sync` is active), fetch the max ID from the `artifacts` table.
    2. **Local Fallback**: configured, scan the local file system (`.agent/cache/stories`, `.agent/cache/plans`) to find the local max.
    3. **Conflict Resolution**: The higher of (Remote Max, Local Max) + 1 is the next ID.
- The Notion Integration (INFRA-052) will respect this by pulling the latest state before creating new Stories.
