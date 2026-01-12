# ADR-004: Pytest and Playwright for Testing

## Status
Accepted

## Context
Reliable automated testing is crucial. We need tools for Unit Testing (Backend) and End-to-End Testing (Frontend/Integration).

## Decision
- **Pytest**: For testing the FastAPI backend. It is the industry standard for Python testing, with powerful fixtures.
- **Playwright**: For End-to-End (E2E) testing of the web application and critical user flows.

## Alternatives Considered
- **Unittest (Python)**:
  - *Pros*: Built-in.
  - *Cons*: Boilerplate heavy.
- **Cypress**:
  - *Pros*: Popular for E2E.
  - *Cons*: Slower than Playwright, historically more flaky.
- **Selenium**:
  - *Pros*: Legacy support.
  - *Cons*: Slow, complex setup.

## Consequences
- **Positive**: Pytest offers clean syntax. Playwright is fast and supports multiple browsers.
- **Negative**: Need to maintain separate test stacks (Python vs TS based Playwright tests, though we seem to be using the Python Playwright bindings in backend/pyproject.toml or TS in web/).
*Correction: The repository currently lists `pytest-playwright` in `backend/pyproject.toml`, implying Python-driven E2E tests, while `web/package.json` also has Playwright. We acknowledge both or favor the one actively used.*
