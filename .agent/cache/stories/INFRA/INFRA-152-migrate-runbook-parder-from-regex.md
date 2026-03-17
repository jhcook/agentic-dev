# INFRA-152: Migrate Runbook Parser From Regex

## State

REVIEW_NEEDED

## Problem Statement

The current markdown parser in `parser.py` relies on custom regex patterns to extract fenced code blocks, split sections, and mask content. This approach is fragile and frequently fails when encountering nested code fences, unanchored header matches, or self-referential content, leading to runbook execution errors and high maintenance overhead.

## User Story

As an **Infrastructure Engineer**, I want **the runbook engine to utilize a standardized CommonMark AST parser** so that **runbooks are parsed reliably regardless of complexity or nesting.**

## Acceptance Criteria

- [ ] **Scenario 1**: Given a runbook with nested fenced code blocks, When the parser processes the file, Then it correctly identifies the outer and inner blocks without truncation or masking errors.
- [ ] **Scenario 2**: Section splitting must rely on the library's AST (Abstract Syntax Tree) to ensure headers are only matched when they are valid Markdown structural elements.
- [ ] **Negative Test**: System handles malformed Markdown (e.g., unclosed fences) gracefully by falling back to safe defaults or providing actionable error logs instead of crashing.

## Non-Functional Requirements

- **Performance**: Parsing latency should remain sub-100ms for standard runbooks (<500 lines).
- **Security**: The library must be configured to disable HTML rendering or any features that allow remote code execution/injection.
- **Compliance**: Parser must adhere to the CommonMark or GFM (GitHub Flavored Markdown) specification.
- **Observability**: Implement detailed logging for parsing failures to identify specific malformed runbook lines.

## Linked ADRs

- ADR-012: Selection of Markdown Library for Runbook Ingestion

## Linked Journeys

- JRN-004: Authoring and Executing Automated Runbooks

## Impact Analysis Summary

- **Components touched**: `parser.py`, `runbook_engine/core.py`
- **Workflows affected**: Runbook ingestion, validation, and execution.
- **Risks identified**: Potential regression if existing "non-standard" runbooks relied on specific regex quirks; minor change in how whitespace or edge-case markdown is interpreted.

## Test Strategy

- **Unit Testing**: Replace regex unit tests with a suite covering nested blocks, varied header styles, and special characters.
- **Regression Testing**: Run the new parser against the existing library of 200+ production runbooks to ensure output parity for core executable blocks.
- **Comparison Tool**: Create a script to diff the output of the regex parser vs. the library parser to identify structural changes.

## Rollback Plan

- Maintain the legacy `_mask_fenced_blocks` and `_extract_fenced_content` methods behind a feature toggle (`USE_LEGACY_PARSER=true`) for immediate reversion in production if critical failures occur.

## Copyright

Copyright 2026 Justin Cook
