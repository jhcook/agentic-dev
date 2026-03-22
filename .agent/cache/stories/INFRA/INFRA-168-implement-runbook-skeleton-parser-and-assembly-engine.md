# INFRA-168: Implement Runbook Skeleton Parser and Assembly Engine

## State

COMMITTED

## Problem Statement

To automate runbook generation, we need to move away from monolithic documents. Currently, there is no mechanism to programmatically decompose a runbook skeleton into addressable segments or re-integrate generated content while preserving the original structure, metadata, and formatting.

## User Story

As an **Infrastructure Engineer**, I want **a system to parse runbook skeletons into addressable blocks and re-assemble them into a final document** so that **I can automate content updates within a consistent, well-formatted framework.**

## Acceptance Criteria

- [x] **Scenario 1**: Implement `parser.py` to parse a valid runbook skeleton (Markdown/YAML) into discrete, addressable block IDs with associated metadata.
- [x] **Scenario 2**: Implement `assembly_engine.py` to reconstruct a complete document from specific block IDs, ensuring original document order, whitespace, and styling are preserved.
- [x] **Negative Test**: Implement error handling in `parser.py` and `assembly_engine.py` to gracefully throw `InvalidTemplateError` on malformed skeletons.
- [x] **Scenario 4**: Pre-merge NEW+MODIFY S/R blocks in-memory before writing, so MODIFY operations targeting NEW files succeed on first run.
- [x] **Scenario 5**: Auto-inject missing module docstrings for NEW and existing files instead of blocking implementation.
- [x] **Scenario 6**: Fuzzy S/R matching fallback — when exact SEARCH text not found, use `difflib.SequenceMatcher` (0.6 threshold) to find best matching region.
- [x] **Scenario 7**: Post-generation S/R validation gate — after AI generates runbook, read actual files from disk and auto-correct hallucinated SEARCH text.
- [x] **Scenario 8**: Non-step `###` header demotion in `autocorrect_runbook_fences` to prevent empty-step schema violations.

## Non-Functional Requirements

- **Performance**: Parsing and assembly of a standard 50-block runbook must complete in < 250ms.
- **Security**: The parser must sanitize input to prevent injection attacks or unauthorized file system traversal via template references.
- **Compliance**: All assembly actions must be logged for auditability (who triggered the assembly and which version of the skeleton was used).
- **Observability**: Provide metrics on parsing success rates and block mapping density. Fuzzy match events are logged with structured `logging.info` / `logging.warning`.

## Linked ADRs

- ADR-012: Selection of Template Parsing Strategy

## Linked Journeys

- JRN-004: Automated Incident Response Document Generation

## Impact Analysis Summary

**Components touched:**
- `.agent/src/agent/core/implement/parser.py` — **[MODIFIED]** S/R block extraction
- `.agent/src/agent/core/implement/tests/test_parser.py` — **[MODIFIED]** Updated test assertions
- `.agent/src/agent/core/implement/assembly_engine.py` — **[NEW]** Document reconstruction engine
- `.agent/src/agent/core/implement/tests/test_assembly_engine.py` — **[NEW]** Assembly engine tests
- `.agent/src/agent/core/implement/tests/test_assembly_benchmarks.py` — **[NEW]** Performance benchmarks
- `.agent/src/agent/core/implement/chunk_models.py` — **[MODIFIED]** RunbookBlock/RunbookSkeleton models
- `.agent/src/agent/core/implement/telemetry_helper.py` — **[MODIFIED]** Assembly audit logging
- `.agent/src/agent/core/implement/guards.py` — **[MODIFIED]** Fuzzy matching, S/R validation gate, header demotion
- `.agent/src/agent/commands/implement.py` — **[MODIFIED]** Pre-merge NEW+MODIFY, docstring auto-fix
- `.agent/src/agent/commands/runbook.py` — **[MODIFIED]** S/R validation gate integration, version check
- `.agent/src/agent/commands/runbook_gates.py` — **[NEW]** Extracted runbook gate logic
- `.agent/src/agent/commands/runbook_generation.py` — **[NEW]** Chunked generation pipeline
- `.agent/docs/runbook_skeleton_spec.md` — **[NEW]** Skeleton specification
- `.agent/docs/runbook_api_usage.md` — **[NEW]** API usage documentation

**Workflows affected:**
- Runbook Creation Workflow (`agent new-runbook`)
- Runbook Implementation Workflow (`agent implement`)
- Automated Documentation Updates

**Risks identified:**
- Potential for formatting drift if the parser does not strictly adhere to spec.
- Fuzzy matching threshold (0.6) may accept false positives on very short S/R blocks.
- Resource contention if large-scale batch assembly occurs.

## Test Strategy

- **Unit Testing**: Validate individual regex/parsing logic for block identification.
- **Integration Testing**: End-to-end "Round Trip" test—parse a skeleton, immediately re-assemble it, and perform a diff to ensure 0% deviation.
- **Contract Testing**: Ensure the output map format matches the requirements of the downstream content generation engine.
- **Fuzzy Match Testing**: Verified `_fuzzy_find_and_replace()` and `validate_and_correct_sr_blocks()` against INFRA-168 runbook (20 blocks checked, 10 auto-corrected).
- **Header Demotion Testing**: Verified non-step headers demoted correctly, Step headers preserved.

## Rollback Plan

- Revert to the previous stable version of the Infrastructure Pipeline.
- Skeleton templates are version-controlled; roll back to the previous tag if schema changes cause assembly failure.

## Copyright

Copyright 2026 Justin Cook
