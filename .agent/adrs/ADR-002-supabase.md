# ADR-002: Supabase as Backend-as-a-Service

## Status
Accepted

## Context
We need a robust, scalable, and secure solution for Authentication, Database (PostgreSQL), and Real-time subscriptions without implementing these primitives from scratch. The team wants to focus on business features rather than database infrastructure hosting.

## Decision
We will use **Supabase** as our primary Backend-as-a-Service provider.
It will handle:
- Authentication (Auth).
- Database (PostgreSQL).
- Storage.
- Real-time events.

## Alternatives Considered
- **Firebase**:
  - *Pros*: Mature, excellent mobile integration.
  - *Cons*: Vendor lock-in (NoSQL), strictly proprietary.
- **AWS Amplify**:
  - *Pros*: Integrates with AWS ecosystem.
  - *Cons*: High complexity, steep learning curve.
- **Custom Dockerized Postgres + Auth Service (Keycloak)**:
  - *Pros*: Full control.
  - *Cons*: High maintenance burden for a small team.

## Consequences
- **Positive**: Rapid development, industry-standard PostgreSQL under the hood, open-source friendly.
- **Negative**: Reliance on 3rd party availability (unless self-hosted), "Supabase-way" constraints for Auth.
