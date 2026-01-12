# Critical Flow Testing Policy

**Version:** 1.0  
**Effective Date:** 2025-12-19  
**Owner:** @QA  

## Purpose

Prevent regressions in critical user workflows by mandating integration tests that exercise real code paths without excessive mocking.

## Background

**Incident:** Commit 746a320 introduced a regression where the Knowledge Base upload endpoint was missing a function call (`result = await _proxy_to_mcp(...)`). This bug:
- ✅ Passed syntax checking (`py_compile`)
- ✅ Passed static analysis (`pyflakes`)
- ✅ Passed unit tests (mocked the broken layer)
- ❌ **Would fail immediately at runtime** with `NameError: name 'result' is not defined`

**Root Cause:** Tests used mocks that bypassed the actual broken code path.

## Policy

### Critical User Flows (Must Always Work)

1. **Knowledge Base Upload** (`POST /api/upsert_document`)
   - Upload document → MCP worker → index → verify
   
2. **Search** (`POST /api/search`)
   - Query → vector search → return results
   
3. **Chat** (`POST /api/chat`)
   - Question → backend → response with session tracking
   
4. **Grounded Answer** (`POST /api/grounded_answer`)
   - Question → RAG pipeline → answer with citations

### Testing Requirements

#### 1. Integration Test Coverage (MANDATORY)

All critical flows MUST have integration tests in `tests/test_critical_flows.py` that:
- Use minimal mocking (only mock external services, not internal logic)
- Exercise the full request → response cycle
- Verify response structure and status codes
- Run against real infrastructure (pgvector, MCP server)

#### 2. Pre-Merge Enforcement

- **GitHub Actions:** Critical tests MUST pass before PR merge
  - No `|| echo` fallbacks allowed
  - Test failures BLOCK merge
  
- **Local Pre-Push Hook:** Runs critical tests before `git push`
  - Installed at `.git/hooks/pre-push`
  - Can be bypassed with `--no-verify` (not recommended)

#### 3. @QA Role Responsibilities

During preflight review, @QA MUST:
- Verify critical flows have test coverage
- Run `pytest tests/test_critical_flows.py -v`
- BLOCK if tests fail or coverage is missing for new endpoints

### When to Add a Critical Flow Test

Add to `test_critical_flows.py` if the feature:
- Is a primary user-facing workflow
- Involves multiple system components (API → backend → database)
- Has caused a production incident or major regression
- Is part of the product's core value proposition

### Test Maintenance

- Review critical flows quarterly
- Update tests when API contracts change
- Remove tests only when features are deprecated
- Keep test execution time < 30 seconds total

## Enforcement Levels

| Check | Trigger | Enforcement |
|-------|---------|-------------|
| Static analysis (pyflakes) | Git pre-commit | BLOCK commit |
| Critical flow tests | Git pre-push | BLOCK push (can override) |
| Full test suite | GitHub Actions PR | BLOCK merge (no override) |

## Exceptions

Critical flow tests may be skipped locally if:
- Working on documentation only
- Infrastructure (pgvector) is not running
- Using `git push --no-verify` with justification

**However:** GitHub Actions will always run critical tests with infrastructure. Local bypasses do not affect CI enforcement.

## Related Documents

- `.agent/commands/preflight.md` - Preflight review process
- `.agent/rules/the-team.mdc` - @QA role definition
- `.github/workflows/preflight.yml` - CI test configuration

## Revision History

- 2025-12-19: Initial policy created after Knowledge Base regression incident
