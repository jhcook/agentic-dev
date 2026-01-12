# ADR-006: Radix UI and Tailwind CSS

## Status
Accepted

## Context
We need a consistent design system that is accessible, easy to style, and supports dark mode without building components from scratch.

## Decision
We will use **Radix UI** (Headless components) combined with **Tailwind CSS** for styling (via `shadcn/ui` patterns if applicable, or direct usage).

## Alternatives Considered
- **Material UI (MUI)**:
  - *Pros*: Complete component set.
  - *Cons*: Hard to override styles, "Google" look.
- **Bootstrap**:
  - *Pros*: Classic.
  - *Cons*: Dated look, heavy.
- **Chakra UI**:
  - *Pros*: Easy to use.
  - *Cons*: Runtime style injection (performance cost).

## Consequences
- **Positive**: maximal accessibility (Radix), maximal styling flexibility (Tailwind), zero-runtime CSS (Tailwind).
- **Negative**: Verbose HTML classes.
