# ADR-007: Expo and React Native

## Status
Accepted

## Context
We need to build a mobile application for iOS and Android. The team specializes in Web technologies (React).

## Decision
We will use **React Native** with **Expo** (Managed Workflow).

## Alternatives Considered
- **Swift/Kotlin (Native)**:
  - *Pros*: Maximum performance.
  - *Cons*: Two separate codebases, requires specialized skills.
- **Flutter**:
  - *Pros*: Performant, consistent UI.
  - *Cons*: New language (Dart), non-native widgets.
- **Bare React Native**:
  - *Pros*: Full native control.
  - *Cons*: Maintenance nightmare for upgrading native deps.

## Consequences
- **Positive**: Single codebase (mostly), simplified builds (EAS), rapid iteration (Expo Go).
- **Negative**: Native modules limited to what Expo supports (though Config Plugins solve most of this).
