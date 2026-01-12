# ADR-009: Expo Router

## Status
Accepted

## Context
Navigation in React Native has historically been complex (React Navigation). We want a file-based routing system similar to Next.js to lower the cognitive load for developers moving between Web and Mobile.

## Decision
We will use **Expo Router**.

## Alternatives Considered
- **React Navigation** (Core):
  - *Pros*: Extremely customized.
  - *Cons*: High boilerplate, imperative definition.

## Consequences
- **Positive**: File-system based routing, automatic deep linking, "Next.js for Native" feel.
- **Negative**: Newer library, potentially fewer community examples than vanilla React Navigation.
