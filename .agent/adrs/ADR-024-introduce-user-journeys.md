# ADR-024: Introduce User Journeys as First‑Class Artifacts

## Status

ACCEPTED

## Context

The current Agentic Dev Framework uses runbooks to orchestrate agent‑driven code generation and updates. Runbooks describe how the agent should perform tasks, but they do not define what the system must do from a product perspective. As a result, product behavior is not represented as a stable, version‑controlled model.

As new features (“stories”) are introduced, there is no mechanism to ensure that previously implemented behaviors remain intact. Because AI‑generated code is probabilistic and context‑sensitive, adding new features can unintentionally modify or overwrite existing logic, leading to regressions.

To support sustainable, iterative, AI‑assisted development, the framework needs a durable, declarative representation of system behavior that agents can rely on when generating or updating code.

## Decision

We will introduce user journeys as first‑class artifacts within the framework. User journeys will be stored as structured files (e.g., YAML) under a new journeys/ directory. Each journey will describe:

- the actor
- the sequence of user and system actions
- expected outcomes
- acceptance criteria
- relevant edge cases

Runbooks will be updated to consume these journey files rather than embedding product behavior directly. Specifically:

1. Feature generation runbooks will parse a journey and generate:

- backend logic
- UI components
- routing
- data models (if applicable)
- acceptance tests derived from the journey

1. Feature update runbooks will:

- diff the updated journey against its previous version
- regenerate only the affected modules
- update tests accordingly

1. Regression detection will rely on the full suite of journey‑derived tests.
When a new journey is added, all existing journeys’ tests will be executed.
If any fail, the agent will be instructed to fix only the failing behavior, not regenerate unrelated code.

This creates a clear separation of concerns:

- Journeys define what the system must do.
- Runbooks define how the agent updates the system.
- Tests enforce the contract defined by journeys.

## Consequences

### Positive

- Regression prevention: Every journey produces acceptance tests. New stories cannot break existing ones without detection.
- Deterministic evolution: Journeys are version‑controlled artifacts, enabling diff‑based updates and predictable regeneration.
- Stable product model: Product behavior is captured declaratively and independently of implementation details.
- Reduced AI drift: Agents operate within clear boundaries defined by journeys and runbooks, reducing unintended rewrites.
- Improved maintainability: Journeys act as living documentation of system behavior, readable by both humans and agents.

### Negative

- Initial overhead: Defining journeys requires upfront effort and discipline.
- Runbook complexity increases: Runbooks must be extended to parse journeys and generate tests.
- Test suite growth: As journeys accumulate, the test suite becomes larger and more resource‑intensive.

## Alternatives Considered

Embedding journeys directly in runbooks  
Rejected because it mixes product intent with procedural instructions, making both brittle.

Using ADRs to represent journeys  
Rejected because ADRs capture architectural decisions, not user behavior or flow logic.

Relying solely on agent reasoning without journeys  
Rejected due to high risk of regressions and non‑deterministic code generation.

## Outcome

Adopting user journeys as first‑class artifacts provides a stable behavioral contract for the system. Combined with journey‑derived tests and runbook‑driven code generation, this approach enables safe, iterative, AI‑assisted development without regressions as new stories are introduced.
