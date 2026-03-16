# INFRA-150: Strict Block-Level Pydantic Rules

## State

COMMITTED

## Problem Statement

The current Pydantic models allow "semantically empty" blocks—such as a `[MODIFY]` block without Search/Replace pairs or `[NEW]` headers without code fences—to pass validation. This results in downstream execution failures or silent errors when the system attempts to process empty instructions.

Parent: INFRA-147

## User Story

As a **backend system**, I want **strict schema validation for all block types** so that **malformed or empty LLM outputs are rejected early in the parsing lifecycle.**

## Acceptance Criteria

- [ ] **Scenario 1**: Given a `SearchReplaceBlock`, When the `search` or `replace` strings are empty or contain only whitespace, Then a validation error is raised and whitespace is stripped.
- [ ] **Scenario 2**: `ModifyBlock` must contain at least one valid `SearchReplaceBlock` in its `blocks` list via a root validator.
- [ ] **Scenario 3**: `DeleteBlock.rationale` must meet a minimum length of 5 characters to ensure meaningful justification.
- [ ] **Negative Test**: System handles a `[NEW]` header without a subsequent code fence by raising a specific `ParsingError` rather than returning an empty object.

## Non-Functional Requirements

- **Performance**: Pydantic validation overhead must remain negligible (<10ms per block).
- **Security**: Prevent injection of whitespace-only content to bypass "required" fields.
- **Compliance**: N/A.
- **Observability**: Ensure `ParsingError` messages include the specific block type and missing requirement for easier debugging of LLM prompts.

## Linked ADRs

- None

## Linked Journeys

- JRN-057: Impact Analysis Workflow
- JRN-062: Implement Oracle Preflight Pattern

## Impact Analysis Summary

- **Components touched**: `models.py` (Pydantic schemas), `parser.py` (Logic for handling malformed headers), `test_models.py` (Unit tests for validators), `test_parser.py` (Integration tests for parser error handling).
- **Journeys modified**: `JRN-057` (Impact Analysis Workflow), `JRN-062` (Implement Oracle Preflight Pattern).
- **Workflows affected**: LLM response processing and automated file editing.
- **Risks identified**: Strict validation may increase the failure rate of poorly tuned LLM prompts that occasionally output empty headers.

## Test Strategy

- **Unit Testing**: Validate `SearchReplaceBlock`, `ModifyBlock`, and `DeleteBlock` with various edge cases (empty strings, whitespace, empty lists).
- **Integration Testing**: Pass malformed markdown strings through the parser to ensure `ParsingError` is raised with the correct context.

## Rollback Plan

Revert changes to `models.py` and `parser.py` to restore lenient validation.

## Copyright

Copyright 2026 Justin Cook
