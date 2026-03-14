# INFRA-135: Dynamic Rule Retrieval — Rule Diet

## State

DRAFT

## Problem Statement

The agent's context window is overwhelmed by ~70KB of static rules across 18 `.agent/rules/` files, plus `GEMINI.md`, `agents.yaml`, and instructions. These are injected wholesale into runbook generation prompts regardless of relevance. This leads to conflicting directives, context confusion, and the LLM ignoring critical rules because they're buried in noise. The `runbook.py` prompt already truncates rules at 3000 chars (line 249) — an admission that the full ruleset doesn't fit.

## User Story

As a **developer**, I want **only the rules relevant to my current change to be injected into the AI's context** so that **the agent focuses on the specific task without being confused by irrelevant governance constraints**.

## Acceptance Criteria

- [ ] **AC-1**: The 18 rule files in `.agent/rules/` are audited and classified into **core** (always-included, ≤5 files) and **contextual** (retrieved on demand).
- [ ] **AC-2**: Core rules are injected directly into the system prompt as today. Contextual rules are stored as NotebookLM sources and/or Vector DB entries.
- [ ] **AC-3**: During codebase introspection in `runbook.py`, a retrieval step queries NotebookLM (via the existing MCP integration) with the targeted file list and story context to fetch only applicable rules.
- [ ] **AC-4**: A fallback mechanism ensures that if retrieval fails (timeout, auth error, empty result), a static "core governance" set (Security + QA minimums) is always included.
- [ ] **AC-5**: The context injected into `runbook.py`'s system prompt is reduced by ≥50% in token count compared to the current baseline.
- [ ] **Negative Test**: With NotebookLM unavailable, the fallback governance set is included and runbook generation does not fail.

## Non-Functional Requirements

- Performance: Retrieval adds ≤ 5s to runbook generation (NotebookLM query).
- Security: Rule content does not leak to external services beyond the already-configured NotebookLM instance.
- Compliance: SOC2 — all retrieval operations logged with source and latency.
- Observability: Structured log event `rule_retrieval` with `source`, `count`, `latency_ms`, `fallback_used` fields.

## Linked ADRs

- ADR-005 (AI-Driven Governance Preflight)

## Linked Journeys

- JRN-065

## Impact Analysis Summary

Components touched: `runbook.py`, `context.py`, `context_builder.py`, `.agent/rules/*`, NotebookLM MCP
Workflows affected: `/runbook`
Risks identified: Retrieval failure could miss critical governance checks — mitigated by fallback static core set.

## Test Strategy

- Unit test: mock NotebookLM query returning relevant rules; verify only those rules appear in the system prompt.
- Unit test: mock NotebookLM failure; verify fallback core governance set is included.
- Integration test: measure token count of system prompt before/after; assert ≥50% reduction.

## Rollback Plan

Re-enable full static rule injection by reverting `runbook.py` context loading to the current approach.

## Copyright

Copyright 2026 Justin Cook
