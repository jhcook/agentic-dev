# Regression Guardrails Epic

## State

COMMITTED

## Related Stories

- INFRA-057: ADR-Driven Deterministic Lint Rules
- INFRA-058: Journey-Linked Regression Tests
- INFRA-059: Impact-to-Journey Mapping
- INFRA-060: Panel Verdict Anchoring
- INFRA-061: ADK Multi-Agent Governance Panel
- INFRA-063: AI-Powered Journey Test Generation

## Related Journeys

- JRN-052: ADR Lint Enforcement
- JRN-053: Journey Test Coverage
- JRN-054: Impact-to-Journey Mapping
- JRN-055: ADK Multi-Agent Panel Review

## Linked ADRs

- ADR-005 (AI-Driven Governance Preflight)
- ADR-021 (Architectural Exception Records)
- ADR-025 (Lazy Initialization)
- ADR-028 (Synchronous CLI Design)

## Summary

Replace advisory-only AI governance with a layered enforcement system. Deterministic
code-based checks (ADR lint, journey test gates, impact-to-journey mapping) catch
regressions without AI, while the governance panel is upgraded to an ADK multi-agent
system with tools, delegation, and loops — then anchored to cite the ADRs and journeys
it considered.

## Story → Journey Map

| Story | Journey | Description |
|---|---|---|
| INFRA-057 | JRN-052 | ADRs declare enforcement blocks → deterministic lint checks |
| INFRA-058 | JRN-053 | Journeys require linked test files → coverage gate |
| INFRA-059 | JRN-054 | Changed files → affected journeys → targeted tests |
| INFRA-060 | JRN-045 | Panel must cite relevant ADRs/journeys |
| INFRA-061 | JRN-055 | Role agents with tools, delegation, loops via ADK |

## Milestones

### Phase 1: Foundations (parallel)

- **M1: ADR Lint (INFRA-057)**
  - Add `enforcement` blocks to ADR markdown files
  - `agent check lint` parses and runs declared patterns
  - Preflight integrates ADR lint as deterministic gate

- **M2: Journey Test Links (INFRA-058)**
  - Schema enforces `implementation.tests` for COMMITTED journeys
  - `agent journey coverage` reports mapping status
  - Preflight blocks on missing journey tests

- **M3: ADK Panel (INFRA-061)**
  - Add `google-adk` optional dependency
  - Each role → ADK `LlmAgent` with tools (read_file, search, list_adrs)
  - `CoordinatorAgent` orchestrates parallel reviews with delegation
  - Existing `AIService` used as model backend (vendor agnostic)
  - Fallback to legacy sequential panel via `council.engine: legacy`

### Phase 2: Integration (depends on Phase 1)

- **M4: Impact → Journey Map (INFRA-059)**
  - Build reverse index: `file → [journey IDs]` from `implementation.files`
  - `agent impact` outputs "Affected Journeys" section
  - Preflight selects required tests based on changeset impact

### Phase 3: Anchoring (depends on Phase 2 + M3)

- **M5: Panel Verdict Anchoring (INFRA-060)**
  - Panel prompt includes relevant ADRs/journeys from impact map
  - Response requires `REFERENCES:` section citing ADR/journey IDs
  - Post-processing validator warns on missing citations

## Architecture

```text
Code Change
    │
    ├─► ADR Lint (M1)                 ← deterministic, code-based
    ├─► Journey Test Gate (M2)        ← deterministic, file existence
    ├─► Impact → Journey Map (M4)     ← deterministic, reverse index
    └─► ADK Panel (M3)               ← AI, multi-agent
          └─► Verdict Anchoring (M5)  ← post-processing validation
```

## Risks & Mitigations

- **Risk:** ADR enforcement patterns produce false positives.
  - **Mitigation:** EXC-* exception records (INFRA-056) suppress known exceptions.
- **Risk:** Backfilling 50+ journeys with `implementation.tests` is labor-intensive.
  - **Mitigation:** Phase the requirement — only enforce for new/COMMITTED journeys.
- **Risk:** ADK dependency pulls in heavy Vertex AI SDK.
  - **Mitigation:** Optional dependency (`agent[adk]`), no `google-cloud-*` packages required.
- **Risk:** Model provider lock-in via ADK.
  - **Mitigation:** ADK is orchestration-only; model calls routed through existing `AIService`.

## Verification

- **Automated:**
  - Per-story unit + integration tests (see individual stories)
  - End-to-end: `agent preflight` runs all gates in sequence
  - Benchmark: ADK panel vs legacy panel runtime
- **Manual:**
  - Regression: existing preflight behavior unchanged with `council.engine: legacy`
  - Validate panel tool use produces actionable findings
