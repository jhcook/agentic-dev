# ADR-010: OpenTelemetry for Observability

## Status
Accepted

## Context
As the application scales, relying solely on logs (`print`, `console.log`) or disconnected monitoring tools makes debugging distributed transactions (e.g., Frontend -> Backend -> Database) difficult. We need a unified standard for tracing, metrics, and logging across our Polyglot stack (Next.js/TypeScript & FastAPI/Python).

## Decision
We will use **OpenTelemetry (OTel)** as the standard for observability.

### Backend (FastAPI)
- Use `opentelemetry-instrumentation-fastapi` and relevant auto-instrumentation packages.
- Export traces to a collector or direct backend (e.g. Jaeger, Honeycomb, or Supabase if supported/configured).

### Frontend (Next.js)
- Use `@vercel/otel` or `@opentelemetry/auto-instrumentations-web`.
- Propagate trace headers to Backend calls.

## Alternatives Considered
- **Proprietary Agents (New Relic, Datadog)**:
  - *Pros*: Easy setup.
  - *Cons*: Vendor lock-in, high cost.
- **Structured Logging only**:
  - *Pros*: Simple.
  - *Cons*: No context propagation (trace IDs) between services.

## Consequences
- **Positive**: Industry standard (CNCF), vendor-neutral, unified trace context.
- **Negative**: setup complexity (collectors), potential performance overhead if over-sampled.
