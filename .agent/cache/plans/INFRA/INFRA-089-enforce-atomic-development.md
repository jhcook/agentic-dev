# INFRA-089 Decomposition Plan: Enforce Atomic Development

## State

ACTIVE

## Parent Story

INFRA-089 — Enforce Atomic Development PR and Commit Size Limits

## Rationale

INFRA-089 estimated at >600 LOC across 5 defence layers, 3 core files, and 4 workflows — well above the 400 LOC atomic PR threshold. Decomposed into 5 independent child stories ordered by dependency (simplest and most foundational first).

## Child Stories (Implementation Order)

| Phase | Story ID | Title | Layer | Est. LOC | Dependencies |
|-------|----------|-------|-------|----------|--------------|
| 1 | INFRA-091 | Static Commit Atomicity Checks | 4 | ~120+100 | None |
| 2 | INFRA-092 | Post-Apply PR Size Gate | 5 | ~60+60 | INFRA-091 |
| 3 | INFRA-093 | Forecast Gate for Runbook Generation | 1 | ~100+80 | None |
| 4 | INFRA-094 | SPLIT_REQUEST Fallback | 2 | ~80+60 | INFRA-093 |
| 5 | INFRA-095 | Micro-Commit Loop and Circuit Breaker | 3 | ~200+120 | INFRA-091 |

## Dependency Graph

```
INFRA-091 (Layer 4: Static Checks)
├── INFRA-092 (Layer 5: PR Size Gate) — uses GateResult + wires into implement.py
└── INFRA-095 (Layer 3: Circuit Breaker) — save-point commits validated by Layer 4

INFRA-093 (Layer 1: Forecast Gate)
└── INFRA-094 (Layer 2: SPLIT_REQUEST) — secondary defence if forecast passes
```

Phases 1-2 and 3-4 can be parallelised. Phase 5 depends on Phase 1.

## Linked Journeys

- JRN-064 — Forecast-Gated Story Decomposition (Phases 3, 4)
- JRN-065 — Circuit Breaker During Implementation (Phases 1, 2, 5)

## Completion Criteria

INFRA-089 is complete when all 5 child stories reach DONE state.

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0
