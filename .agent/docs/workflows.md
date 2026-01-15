# Workflows

## Story-Driven Development

We follow a linear workflow to ensure governance:

1.  **Plan**: Define the high-level objective.
2.  **Story**: Break down the objective into specific user stories.
    - Status: `DRAFT` -> `OPEN` -> `COMMITTED`.
3.  **Runbook**: Create a technical implementation guide for a story.
    - Status: `DRAFT` -> `ACCEPTED`.
4.  **Implementation**: Write code.
5.  **Preflight**: Verify code against rules.
6.  **PR**: Submit for review.

## Sync Workflow

1.  Author a story locally.
2.  `agent sync push`.
3.  Teammate runs `agent sync pull`.
4.  Teammate reviews and updates the story.
5.  Teammate runs `agent sync push`.
