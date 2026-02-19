# INFRA-066: Add Source Code Context to Runbook Generation

## State

COMMITTED

## Problem Statement

The `agent new-runbook` command generates implementation runbooks with inaccurate file paths, wrong SDK usage, and generic code snippets that don't match the actual codebase. Root cause: `context_loader.load_context()` provides only governance context (rules, agents, ADRs, role instructions) — **no source code or file tree is included**. The AI is asked to write implementation-level detail with zero visibility into the repository's actual source structure.

Observed symptoms:

- Invented paths like `src/service.py` instead of actual `.agent/src/agent/core/ai/service.py`
- Used the deprecated `google-generativeai` SDK instead of the `google-genai` SDK actually in the codebase
- Produced generic implementation steps that don't follow existing code patterns (e.g., standalone functions instead of class methods)
- Pre-checked verification items that should be unchecked

## User Story

As a developer using `agent new-runbook`, I want the generated runbook to reference accurate file paths and match the actual codebase patterns, so that the runbook is directly actionable without manual rewriting.

## Acceptance Criteria

- [ ] **AC1: File Tree**: Given a story, when `agent new-runbook` is invoked, then the AI prompt includes a file tree of the source directory (`{agent_dir}/src/`).
- [ ] **AC2: Targeted Source Snippets**: Given a story with identifiable affected components, when `agent new-runbook` is invoked, then the AI prompt includes relevant source file content (class signatures, method signatures, imports) from affected files.
- [ ] **AC3: Token Budget**: The combined source context (tree + snippets) must not exceed a configurable character limit (default: 8000 chars) to stay within provider token limits.
- [ ] **AC4: Accurate Output**: Given source code context, when a runbook is generated, then file paths in implementation steps match actual repository paths.
- [ ] **AC5: Graceful Degradation**: If the source directory does not exist or is empty, the runbook generation must still succeed with the existing governance-only context.
- [ ] **Negative Test**: If source files are too large, content is truncated with a clear marker (e.g., `[...truncated...]`).

## Non-Functional Requirements

- **Performance**: Source context loading should add < 500ms to generation time.
- **Security**: Source content must pass through `scrub_sensitive_data()` before inclusion in the prompt.
- **Compliance**: No secrets, API keys, or PII in source context.
- **Observability**: Log source context size at DEBUG level.

## Linked ADRs

- ADR-025: Lazy initialization pattern

## Linked Journeys

- (none yet)

## Impact Analysis Summary

Components touched: `context.py`, `runbook.py`
Workflows affected: `agent new-runbook`
Risks identified: Token budget overflow if source tree is very large; mitigated by configurable char limit and truncation.

## Test Strategy

- **Unit test**: Verify `_load_source_tree()` returns expected tree structure for a known directory.
- **Unit test**: Verify `_load_source_snippets()` extracts class/method signatures within budget.
- **Unit test**: Verify `load_context()` includes `source_tree` and `source_code` keys.
- **Integration test**: Run `agent new-runbook` on an existing committed story and verify file paths in output match actual paths.

## Rollback Plan

Revert changes to `context.py` and `runbook.py`. The feature is additive — removing source context from the prompt returns to the current behavior.
