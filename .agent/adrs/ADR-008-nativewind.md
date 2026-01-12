# ADR-008: NativeWind for Mobile Styling

## Status
Accepted

## Context
We want to share styling knowledge (and potentially tokens) between the Web (Tailwind) and Mobile apps.

## Decision
We will use **NativeWind**. It allows writing Tailwind CSS classes in React Native components.

## Alternatives Considered
- **StyleSheet.create**:
  - *Pros*: Native standard.
  - *Cons*: No relation to web CSS, verbose.
- **Styled Components**:
  - *Pros*: Component-scoped.
  - *Cons*: Runtime overhead.

## Consequences
- **Positive**: Unifies styling syntax across Web and Mobile.
- **Negative**: Some Tailwind classes don't map 1:1 to Native views.
