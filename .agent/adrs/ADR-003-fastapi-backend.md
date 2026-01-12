# ADR-003: FastAPI for Backend Services

## Status
Accepted

## Context
We require a high-performance backend framework to handle API requests, perform background jobs, and potentially integrate with Data Science/AI libraries in the future.

## Decision
We will use **FastAPI** (Python).
- It provides native AsyncIO support.
- It uses Pydantic for data validation (shared knowledge with our data models).
- Automatic OpenAPI documentation generation.

## Alternatives Considered
- **Django**:
  - *Pros*: "Batteries included", ORM built-in.
  - *Cons*: Heavier, synchronous by default (though Async support exists now), less modern API-first feel.
- **Express.js (Node)**:
  - *Pros*: Shared language with frontend (JS/TS).
  - *Cons*: No native Pydantic/Type hints as strong as Python's for AI/ML integration later.

## Consequences
- **Positive**: High performance, type safety, excellent documentation, easy AI integration.
- **Negative**: Context switching between Typescript (Frontend) and Python (Backend).
