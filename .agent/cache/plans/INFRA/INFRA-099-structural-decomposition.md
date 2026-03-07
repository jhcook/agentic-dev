# INFRA-099: Structural Decomposition of Agent Codebase

This plan decomposes the **INFRA-099** refactor into focused child stories. Each story targets one monolithic file, keeping changes within the circuit breaker limits while maintaining a functional system at each step.

## Architecture

See **ADR-041: Module Decomposition Standards** for the 500 LOC ceiling, import hygiene rules, and enforcement mechanisms.

## Execution Order

Bottom-up: start with the least-dependent modules and move toward the UI layer.

### Phase 1: Core Services

| Story | Target File | Decomposition |
|---|---|---|
| **INFRA-100** | `core/ai/service.py` (1,169 LOC) | → `service.py` + `streaming.py` + `providers.py` |
| **INFRA-108** | `core/ai/providers.py` (812 LOC) | → `providers/{openai,vertex,anthropic,ollama,gh}.py` + factory (descoped from INFRA-100) |
| **INFRA-101** | `core/governance.py` (1,988 LOC) | → `governance/{panel,roles,validation}.py` |

### Phase 2: Commands

| Story | Target File | Decomposition |
|---|---|---|
| **INFRA-102** | `commands/implement.py` (1,819 LOC) | → `implement.py` + `core/implement/{orchestrator,circuit_breaker}.py` |
| **INFRA-103** | `commands/check.py` (1,768 LOC) | → `check.py` + `core/check/{system,quality}.py` |

### Phase 3: UI and Onboarding

| Story | Target File | Decomposition |
|---|---|---|
| **INFRA-104** | `tui/app.py` (2,008 LOC) | → `app.py` + `prompts.py` + `chat.py` |
| **INFRA-105** | `commands/onboard.py` (1,060 LOC) | → `onboard.py` + `core/onboard/steps.py` |

### Phase 4: Enforcement

| Story | Target File | Decomposition |
|---|---|---|
| **INFRA-106** | CI + Documentation | LOC enforcement script, import check, README updates |

### Phase 5: Hardening & Cleanup (added post-sprint)

| Story | Target File | Decomposition |
|---|---|---|
| **INFRA-108** | `core/ai/providers.py` (812 LOC) | Protocol-based refactor → `providers/{openai,vertex,anthropic,ollama,gh}.py` + factory |
| **INFRA-109** | `core/implement/orchestrator.py` | Fix `resolve_path` trusted-prefix short-circuit to prevent fuzzy match overwrites |
| **INFRA-110** | `commands/check.py` | Complete check.py decomposition to ≤500 LOC; ADC fallback, diff truncation, provider warning (AC-4/5/6 done in INFRA-103) |

## Dependencies

```
INFRA-100 ──┬── INFRA-108 (depends on INFRA-100's providers.py output)
INFRA-101 ──┤
INFRA-102 ──┤── all others independent, can run in any order
INFRA-103 ──┤
INFRA-104 ──┤
INFRA-105 ──┘
             └── INFRA-106 (must run last among Phase 1-4)

INFRA-108   ── depends on INFRA-100 (providers.py refactor)
INFRA-109   ── independent (path resolution fix)
INFRA-110   ── depends on INFRA-103 (completes check.py extraction)
```

## Copyright

Copyright 2026 Justin Cook
