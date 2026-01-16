# INFRA-012: Refactor Codebase Utilities

Status: ACCEPTED

## Goal Description
The objective is to consolidate common utility functions into `agent.core.utils` to eliminate code duplication, achieve consistency in error handling and type hinting, and reduce maintenance overhead for the `agent` CLI system. This refactor will ensure all commands leverage shared utilities and are easier to maintain and extend.

## Panel Review Findings

- **@Architect**:  
  Consolidating utilities aligns with good design principles, improves modularity, and reduces technical debt. However, care must be taken to avoid overloading `agent.core.utils`, which might grow unwieldy. If the file becomes too large, splitting into smaller modules (`file_helpers`, `text_helpers`, etc.) should be enforced.

- **@Security**:  
  The refactor introduces minor risks in scrubbing sensitive data. Review of `scrub_sensitive_data` must ensure it covers all sensitive patterns. Additionally:
  - Directory traversal must be mitigated when working with paths.
  - Error messages should reveal minimal information to users (e.g., no full paths).

- **@QA**:  
  A comprehensive test plan covering all modified commands and utility functions is crucial. Regression risks are moderate given the connection to multiple commands, so both unit and integration testing must be emphasized. Ensure that all error handling pathways are tested.

- **@Docs**:  
  As utilities are consolidated, their usage must be explained clearly. Docstrings should follow PEP-257, and developer documentation should include examples for commonly-used utilities. Command-specific documentation must also reflect the changes.

- **@Compliance**:  
  This refactor is internal-facing; however, it is critical to not violate preexisting ADRs or other governance constraints. Verify that any reference to removed or renamed utilities is updated accordingly to maintain consistency.

- **@Observability**:  
  Ensure structured logging is adhered to and validate that any newly introduced logs do not include sensitive user data. Metrics should track usage frequency of consolidated utilities to measure their effectiveness post-refactor.

## Implementation Steps

### Audit Phase
#### [NEW] Audit Utility Usage
1. Inspect all `agent/commands/*.py` to identify utility functions with similar or duplicated logic.
2. Catalog how each command leverages the existing utility functions in `agent.core.utils`.

### Consolidation Phase
#### [MODIFY] agent/core/utils.py
1. Refactor utility functions ensuring:
   - Type hints are added (PEP-484 compliance).
   - Docstrings follow PEP-257.
   - Error handling aligns with the outlined Error Handling Strategy (e.g., raising `FileNotFoundError` or `ValueError` as appropriate).

2. Consolidate all utility functionality currently embedded in command files into `agent.core.utils`.

3. Split `agent/core/utils.py` into multiple files if it exceeds 500 lines:
   - `agent/core/utils/file_helpers.py`: File-related operations like `find_story_file`.
   - `agent/core/utils/text_helpers.py`: Text processing like `scrub_sensitive_data`.
   - `agent/core/utils/id_helpers.py`: ID generation and inference like `get_next_id`.

### Migration Phase
#### [MODIFY] agent/commands/*.py
1. Replace all inline implementations of utility logic (`find_story_file`, `scrub_sensitive_data`, etc.) with imports from `agent.core.utils`.
2. Ensure import paths are consistent and avoid circular imports.
3. Update each command to handle errors consistently (raising exceptions vs returning `None`).

### Testing Phase
#### [NEW] tests/core/test_utils.py
1. Write unit tests for:
   - `find_story_file`: Test valid, invalid, and not-found scenarios.
   - `scrub_sensitive_data`: Test diverse patterns of sensitive input.
   - `get_next_id`: Test sequential ID generation logic.
   - Other utility functions based on their primary functionality.

2. Verify integration tests for all commands behave identically pre- and post-refactor.

### Documentation Phase
#### [MODIFY] README.md
1. Update developer guides to document common utilities with practical examples.
2. Add inline usage examples to `agent.core.utils` docstrings.

#### [MODIFY] CHANGELOG.md
1. Document the internal refactor and changes to utility functions.

## Verification Plan

### Automated Tests
- [ ] Unit tests validate each utility function in `agent.core.utils`.
- [ ] Integration tests confirm all commands use the consolidated utilities as intended.

### Manual Verification
- [ ] Validate scrubbing of sensitive data for edge cases manually.
- [ ] Validate error messages for scenarios like missing or malformed IDs.
- [ ] Manual walkthrough of commands (`check.py`, `runbook.py`, etc.) to ensure UI/UX remains unaffected.

## Definition of Done

### Documentation
- [ ] CHANGELOG.md updated with details of the refactor.
- [ ] README.md updated with documented utility functions and examples.
- [ ] All utility functions include PEP-257 docstrings.

### Observability
- [ ] Logs during file operations avoid revealing sensitive data (e.g., absolute paths or PII).
- [ ] Metrics for utility usage are logged and available for monitoring.

### Testing
- [ ] 100% unit-test coverage for utility functions.
- [ ] All existing integration tests pass without modification.
- [ ] Regression tests indicate behavior consistency across commands.

### Governance Compliance
- [ ] No ADRs were modified inconsistent with `adr-standards.mdc`.
- [ ] No external API contracts changed validating compliance with `api-contract-validation.mdc`.