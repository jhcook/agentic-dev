# ADR-005: Next.js App Router

## Status
Accepted

## Context
The web application requires a modern React framework that supports Server Side Rendering (SSR), SEO, and performant routing.

## Decision
We will use **Next.js** with the **App Router** (`app/` directory).

## Alternatives Considered
- **React Router (SPA)**:
  - *Pros*: Simple, static export easy.
  - *Cons*: Worse SEO out of box, initial load time slower.
- **Next.js Pages Router**:
  - *Pros*: Stable, legacy standard.
  - *Cons*: Deprecated favoring App Router, less flexible layouts.

## Consequences
- **Positive**: React Server Components (RSC), streamlined data fetching, automatic code splitting.
- **Negative**: Learning curve for App Router paradigms (server vs client components).
