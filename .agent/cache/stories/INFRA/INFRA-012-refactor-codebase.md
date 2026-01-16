# INFRA-012: Refactor Codebase Utilities

## Parent Plan
INFRA-008

## State
COMMITTED

## Problem Statement
There is code duplication and inconsistency in how the agent CLI handles common operations like finding story files, scrubbing sensitive data, and generating IDs. While some utilities exist in `agent.core.utils`, not all commands use them consistently, leading to:
- Duplicated logic across command files
- Inconsistent error handling
- Harder maintenance (bug fixes must be applied in multiple places)
- Difficult onboarding for new contributors

**Current State:**
- `find_story_file` exists in `utils.py` but some commands may have inline implementations
- `scrub_sensitive_data` exists but usage patterns vary
- Import statements are inconsistent across commands

**Desired State:**
- All common utilities consolidated in `agent.core.utils`
- Consistent usage across all commands
- Clear error handling and type hints
- Comprehensive documentation

## User Story
As a maintainer, I want common logic consolidated in `agent.core.utils` so that:
- New commands can reuse existing functionality without duplication
- Bug fixes apply consistently across all commands
- Code reviews are faster (less duplication to check)
- New contributors can easily find and use utilities

## Acceptance Criteria
- [ ] Audit complete: All duplicated functions identified and documented
- [ ] All commands use utilities from `agent.core.utils` consistently
- [ ] No inline implementations of `find_story_file`, `find_runbook_file`, `scrub_sensitive_data`
- [ ] All utility functions have type hints (PEP-484 compliant)
- [ ] All utility functions have PEP-257 compliant docstrings
- [ ] Error handling is consistent (raise exceptions vs return None documented)
- [ ] All utility functions have unit tests
- [ ] Integration tests verify all commands still work correctly
- [ ] No circular import issues introduced

## Technical Requirements

### Utility Functions to Audit
Based on codebase analysis, the following utilities exist in `agent.core.utils`:
- `find_story_file(story_id: str) -> Optional[Path]`
- `find_runbook_file(runbook_id: str) -> Optional[Path]`
- `scrub_sensitive_data(text: str) -> str`
- `get_next_id(scope: str) -> str`
- `sanitize_title(title: str) -> str`
- `infer_story_id() -> Optional[str]`
- `find_best_matching_story(changed_files: List[str]) -> Optional[str]`

### Commands Using Utilities
- `check.py` - Uses `infer_story_id`, `scrub_sensitive_data`
- `runbook.py` - Uses utilities (needs verification)
- `implement.py` - Uses utilities (needs verification)
- `workflow.py` - Uses `infer_story_id`, `scrub_sensitive_data`, `find_best_matching_story`
- `match.py` - Uses `find_best_matching_story`
- `story.py` - Uses `get_next_id`, `sanitize_title`
- `plan.py` - Uses `get_next_id`, `sanitize_title`
- `adr.py` - Uses `get_next_id`, `sanitize_title`
- `list.py` - Uses `scrub_sensitive_data`

### Error Handling Strategy
- **File not found**: Raise `FileNotFoundError` with descriptive message
- **Invalid ID format**: Raise `ValueError` with format requirements
- **Path validation**: Ensure paths are within `.agent/cache/` to prevent traversal
- **Encoding errors**: Handle gracefully with fallback to 'ignore' mode

### Type Hints Requirements
All functions must have:
- Parameter type hints
- Return type hints
- Optional types where applicable
- No `Any` types unless absolutely necessary

## Impact Analysis Summary

**Components Touched:**
- `agent/core/utils.py` - Consolidate and enhance utilities
- `agent/commands/check.py` - Verify consistent usage
- `agent/commands/runbook.py` - Verify consistent usage
- `agent/commands/implement.py` - Verify consistent usage
- `agent/commands/workflow.py` - Verify consistent usage
- `agent/commands/match.py` - Verify consistent usage
- `agent/commands/story.py` - Verify consistent usage
- `agent/commands/plan.py` - Verify consistent usage
- `agent/commands/adr.py` - Verify consistent usage
- `agent/commands/list.py` - Verify consistent usage

**Workflows Affected:**
- All CLI commands (internal refactor, no user-facing changes)

**Risks Identified:**
- **Regression Risk (MEDIUM)**: Changes to utility functions could break multiple commands
- **Import Cycle Risk (LOW)**: If utils imports from commands, creates circular dependency
- **Performance Risk (LOW)**: File searching logic changes could impact performance
- **Breaking Changes (NONE)**: Internal refactor only, no API changes

**Mitigation Strategies:**
- Comprehensive unit tests for each utility function
- Integration tests for all commands before/after refactor
- Code review focusing on error handling consistency
- Gradual rollout (one command at a time if needed)

## Test Strategy

### Unit Tests (New)
Create `tests/core/test_utils.py`:
- **`test_find_story_file_valid_id`**: Test with valid story ID
- **`test_find_story_file_invalid_id`**: Test with malformed ID
- **`test_find_story_file_not_found`**: Test with non-existent story
- **`test_find_runbook_file_valid_id`**: Test with valid runbook ID
- **`test_scrub_sensitive_data_patterns`**: Test with various PII patterns
- **`test_scrub_sensitive_data_empty`**: Test with empty string
- **`test_get_next_id_sequence`**: Test ID generation
- **`test_sanitize_title_special_chars`**: Test title sanitization
- **`test_infer_story_id_from_branch`**: Test branch name parsing
- **`test_find_best_matching_story`**: Test file matching logic

### Integration Tests (Existing + New)
Verify all commands still work:
- `agent preflight --story INFRA-012` - Uses `find_story_file`
- `agent runbook INFRA-012` - Uses `find_story_file`, `find_runbook_file`
- `agent implement INFRA-012` - Uses `find_runbook_file`
- `agent panel INFRA-012` - Uses `find_story_file`, `scrub_sensitive_data`
- `agent impact INFRA-012` - Uses `find_story_file`, `scrub_sensitive_data`
- `agent new-story` - Uses `get_next_id`, `sanitize_title`
- `agent commit --ai` - Uses `infer_story_id`, `scrub_sensitive_data`

### Regression Tests
- Compare output before/after refactor for identical inputs
- Verify error messages remain consistent
- Ensure no behavioral changes

### Performance Tests
- Benchmark `find_story_file` with 100+ stories
- Verify file searching completes in <100ms

## Implementation Notes

### Proposed Changes
1. **Audit Phase**: Document all current utility usage patterns
2. **Consolidation Phase**: Ensure all utilities are in `utils.py` with proper signatures
3. **Migration Phase**: Update commands to use consolidated utilities
4. **Testing Phase**: Run comprehensive test suite
5. **Documentation Phase**: Update docstrings and add usage examples

### File Organization
Keep `agent/core/utils.py` as a single module for now. If it grows beyond 500 lines, consider splitting into:
- `agent/core/utils/file_helpers.py` - File finding utilities
- `agent/core/utils/text_helpers.py` - Scrubbing, sanitization
- `agent/core/utils/id_helpers.py` - ID generation, inference

### Rollback Plan
If issues are discovered:
1. Revert commits related to refactor
2. Re-run integration tests to verify rollback
3. Document issues for future attempt

### Success Criteria
- All unit tests pass
- All integration tests pass
- No increase in command execution time
- Code coverage maintained or improved
- No new linting errors
