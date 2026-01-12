# ADR-001: Monorepo Structure

## Status
Accepted

## Context
As the "Inspected" application grows, we have distinct codebases for the Backend (API), Web, and Mobile. Maintaining them in separate repositories creates friction in simplified dependency management, CI/CD coordination, and sharing common assets or documentation. We need a strategy to manage these related projects effectively.

## Decision
We will use a **Monorepo** structure.
- `backend/`: Python/FastAPI code.
- `web/`: Next.js web application.
- `mobile/`: React Native / Expo mobile application.
- `.agent/`: Centralized governance and AI instructions.

## Alternatives Considered
- **Polyrepo**: Keeping each project in a separate repo.
  - *Pros*: Clear separation, independent versioning.
  - *Cons*: Difficult to synchronize changes across stack, duplicated CI configuration, context switching.

## Consequences
- **Positive**: Single source of truth, atomic commits across stack, easier code sharing (potentially), unified governance.
- **Negative**: Repo size grows larger, CI build times potentially longer if not optimized (e.g., using Nx or filtering).
