# INFRA-090: Improve AI Prompt Engineering Alignment

## State

COMMITTED

## Problem Statement

An alignment analysis against the "Anatomy of a Claude Prompt" framework — an industry reference for structured AI prompting — revealed that while this project's governance system implements or exceeds all 8 core prompt engineering components, three specific gaps reduce AI agent effectiveness:

1. **No Conversational Clarification Gate** — When the runbook or implement agents encounter ambiguous Acceptance Criteria or vague requirements, they proceed with assumptions rather than pausing to ask the user for clarification. This produces runbooks built on incorrect assumptions that require manual revision cycles.
2. **No Reference Examples** — Templates define *structure* but not *quality*. There are no "gold standard" examples that agents can reverse-engineer patterns from, leading to inconsistent output quality across generated stories and runbooks.
3. **No Explicit Anti-Pattern Definitions** — Rules like `401-no-stubs.mdc` enforce constraints programmatically, but the agent's prompt flow lacks explicit "Does NOT sound like" output-shaping directives that prevent generic, shallow, or placeholder-heavy outputs.

## User Story

As a **developer using the agentic-dev framework**, I want **the AI agents to ask clarifying questions when requirements are ambiguous, reference gold-standard examples when generating artifacts, and avoid known anti-patterns in their output** so that **generated stories, runbooks, and code are higher quality, better aligned with intent, and require fewer revision cycles**.

## Acceptance Criteria

- [ ] **AC-1 (Clarification Gate — Runbook)**: Given a story with ambiguous or untestable Acceptance Criteria, When the runbook agent processes it, Then it emits a `CLARIFICATION_REQUEST` with numbered questions instead of proceeding. The framework parses this, presents questions to the user, and resumes only after answers are incorporated.
- [ ] **AC-2 (Clarification Gate — Implement)**: Given a runbook with an ambiguous or contradictory step, When the implement agent encounters it, Then it pauses and emits a `CLARIFICATION_REQUEST` rather than making assumptions.
- [ ] **AC-3 (Reference Examples)**: Given the `.agent/examples/` directory, Then it contains at least one gold-standard story (`example-story.md`) and one gold-standard runbook (`example-runbook.md`). Agent system prompts reference these as style and quality exemplars.
- [ ] **AC-4 (Anti-Pattern Rule)**: Given a new rule file `403-output-anti-patterns.mdc`, Then it explicitly lists output anti-patterns: stub implementations, placeholder text, vague "TBD" sections, generic boilerplate, and overly verbose explanations. Preflight enforces these.
- [ ] **AC-5 (Success Brief in Runbook Template)**: Given the runbook template, Then it includes a `## Success Brief` section defining: output format expectations, what the output should NOT sound like, and what success looks like for the implementer.
- [ ] **Negative Test**: Given a story with clear, testable Acceptance Criteria, When it is processed by the runbook agent, Then it proceeds through the pipeline without triggering unnecessary clarification requests.

## Non-Functional Requirements

- Performance: Clarification detection must add <2s to runbook/implement startup (lightweight AI call or heuristic check).
- Security: No sensitive data exposed in `CLARIFICATION_REQUEST` payloads.
- Compliance: Clarification requests and their resolutions are audit-logged (SOC2 traceability).
- Observability: Structured logs for `CLARIFICATION_REQUEST` events including story ID, question count, and resolution time.

## Linked ADRs

- ADR-005 (AI-Driven Governance Preflight)

## Linked Journeys

- JRN-XXX

## Impact Analysis Summary

Components touched: `runbook.py`, `implement.py`, runbook/story templates, `.agent/rules/`, `.agent/examples/` (new)
Workflows affected: `/runbook`, `/implement`, `/story`
Risks identified: Over-sensitive clarification detection causing unnecessary pauses; false positives on the "And" test for legitimate compound AC; balancing thoroughness vs. flow interruption

## Test Strategy

- Unit: `CLARIFICATION_REQUEST` emission and parsing in `runbook.py` when given ambiguous AC
- Unit: `CLARIFICATION_REQUEST` emission in `implement.py` when given contradictory steps
- Unit: Anti-pattern rule file (`403-output-anti-patterns.mdc`) is loaded and applied during preflight
- Unit: Clear stories pass through without triggering clarification (negative test)
- Integration: End-to-end with a deliberately ambiguous story → verify clarification is requested before runbook generation proceeds
- Integration: End-to-end with a clear story → verify no clarification interruption

## Rollback Plan

Revert changes to `runbook.py`, `implement.py`, templates, and rule files. Remove `.agent/examples/` directory. No migrations or config schema changes required.

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0
