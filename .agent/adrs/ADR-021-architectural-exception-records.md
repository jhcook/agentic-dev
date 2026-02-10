# ADR-021: Architectural Exception Records

## Status
Accepted

## Context

The governance preflight system (ADR-005) enforces architectural, security, compliance, and quality rules via role-based reviews. However, governance rules can produce **false positives** or **debatable findings** where a deliberate design choice conflicts with a general rule.

Currently, there is no formal mechanism to persist a rebuttal. This causes:

1. **Recurring challenges**: The same finding is raised every preflight run, wasting review cycles.
2. **No audit trail**: Verbal or ad-hoc rebuttals are not captured for SOC 2 evidence.
3. **Ambiguity**: Developers cannot tell whether a deviation was approved or simply overlooked.

## Decision

We introduce **Exception Records** (`EXC-*`) as a formal subtype of ADR, stored alongside standard ADRs in `.agent/adrs/`.

### 1. Format

Exception Records follow the standard ADR lifecycle (Draft → Accepted → Superseded → Retired) with additional required fields:

| Field | Description |
|-------|-------------|
| **Challenged By** | The governance role(s) that raised the finding (e.g. `@Architect`) |
| **Rule Reference** | The specific rule or standard being deviated from |
| **Affected Files** | Files or modules covered by the exception |
| **Justification** | The technical rationale for the deviation |
| **Conditions** | When the exception should be re-evaluated (scope change, refactor, etc.) |

A template is provided at `.agent/templates/exception-template.md`.

### 2. Naming Convention

Exception Records use the prefix `EXC-` followed by a sequential number:

```
EXC-001-update-story-state-location.md
EXC-002-extract-json-function-length.md
```

### 3. Preflight Integration

The `/preflight` workflow loads all `EXC-*` files with status `Accepted` before role reviews. If a role's finding matches an active exception record, the finding is downgraded from `BLOCK` to `APPROVE` with a reference to the exception.

### 4. Lifecycle

- **Accepted**: The exception is active and suppresses matching preflight challenges.
- **Superseded**: A newer exception or resolution replaces it.
- **Retired**: The deviation has been resolved (code was refactored, rule was updated, etc.). The exception no longer suppresses challenges.

Exception records follow the same immutability and change-logging rules as standard ADRs (see `adr-standards.mdc`).

## Alternatives Considered

- **Option A — Ad-hoc cache files**: Rebuttals stored in `.agent/cache/rebuttals/`. Lightweight but not auditable, no lifecycle management, and not integrated with preflight.
- **Option B — Inline code comments**: Adding `# EXCEPTION: ...` comments in code. Doesn't scale, no central registry, no lifecycle.

## Consequences

### Positive
1. **Audit trail**: Every deviation is documented with justification and review conditions — satisfies SOC 2 evidence requirements.
2. **No recurring false positives**: Preflight skips challenges covered by active exceptions.
3. **Lifecycle management**: Exceptions can be retired when the underlying issue is resolved, preventing stale exemptions.

### Negative
1. **Overhead**: Creating an exception record for trivial findings adds friction. (Mitigation: Reserve exceptions for BLOCK-level findings only.)
2. **Stale exceptions**: If conditions are not reviewed, exceptions may outlive their validity. (Mitigation: The `Conditions` field documents when to re-evaluate.)
