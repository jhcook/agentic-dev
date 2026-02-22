# INFRA-013: Optimize Sync for Large Datasets

## Parent Plan
INFRA-008

## State
COMMITTED

## Problem Statement
The `env -u VIRTUAL_ENV uv run agent sync` command loads all artifacts into memory and does not handle pagination. This will fail with large datasets (1000+ artifacts), causing:
- Out of memory errors
- Slow sync times
- Poor user experience with no progress feedback
- No ability to resume interrupted syncs

**Current Limitations:**
- All artifacts loaded into memory at once
- No pagination support in Supabase queries
- No chunking for uploads
- No progress indicators
- No resume capability

**Desired State:**
- Efficient pagination for fetches (cursor-based)
- Chunked uploads to avoid memory issues
- Progress reporting during sync
- Resume capability for interrupted syncs
- Memory usage <500MB for 10K artifacts
- Sync time <5 minutes for 1K artifacts

## User Story
As a user with a large repository (1000+ artifacts), I want:
- `env -u VIRTUAL_ENV uv run agent sync` to complete successfully without running out of memory
- Clear progress indicators showing sync status (e.g., "Syncing 500/1000 artifacts...")
- Ability to resume if sync is interrupted
- Reasonable sync time (<5 minutes for 1K artifacts)

So that I can:
- Sync my entire repository without manual intervention
- Work confidently knowing my data is backed up
- Avoid frustration from failed syncs

## Acceptance Criteria

### Core Functionality
- [ ] `env -u VIRTUAL_ENV uv run agent sync pull` uses cursor-based pagination when fetching from Supabase
- [ ] `env -u VIRTUAL_ENV uv run agent sync push` chunks uploads into batches
- [ ] Page size: 100 artifacts (configurable via environment variable)
- [ ] Maximum page size: 1000 (hard limit enforced)
- [ ] Stream results instead of loading all into memory
- [ ] Process each page before fetching next

### Error Handling
- [ ] Retry failed pages up to 3 times with exponential backoff
- [ ] Fail fast on authentication errors
- [ ] Log all errors with context (page number, offset, error message)
- [ ] Resume from last successful page on interruption

### User Experience
- [ ] Display progress: "Syncing artifacts: 234/1000 (23%)"
- [ ] Show estimated time remaining
- [ ] Allow cancellation with Ctrl+C
- [ ] Resume interrupted syncs automatically
- [ ] Display summary: "Synced 1000 artifacts in 2m 34s"

### Security
- [ ] Pagination respects Supabase RLS policies
- [ ] Rate limiting applied per-user, not per-request
- [ ] Maximum page size enforced to prevent abuse
- [ ] Cursor tokens validated and time-limited

### Performance
- [ ] Memory usage <500MB for 10K artifacts
- [ ] Sync time <5 minutes for 1K artifacts
- [ ] No memory leaks during long-running syncs

## Technical Requirements

### Supabase Pagination
- Use cursor-based pagination with `.range(start, end)`
- Page size: 100 artifacts (configurable via `AGENT_SYNC_PAGE_SIZE` env var)
- Maximum page size: 1000 (hard limit)
- Retry failed pages up to 3 times with exponential backoff (1s, 2s, 4s)

### Memory Management
- Stream results instead of loading all into memory
- Process each page before fetching next
- Clear processed data from memory after each page
- Target: <500MB peak memory for 10K artifacts

### Error Handling Strategy
- **Transient errors** (network, timeout): Retry with exponential backoff
- **Auth errors**: Fail fast with clear message
- **API errors**: Log and skip page, continue with next
- **Interruption**: Save progress, resume from last successful page

### Progress Reporting
- Update progress after each page: "Syncing: 234/1000 (23%)"
- Calculate ETA based on average page processing time
- Display final summary with total time and artifact count

## Impact Analysis Summary

**Components Touched:**
- `agent/sync/sync.py` - Add pagination and chunking logic
- `agent/core/config.py` - Add configuration for page size
- Tests for sync functionality

**Workflows Affected:**
- `env -u VIRTUAL_ENV uv run agent sync pull` - Now paginated
- `env -u VIRTUAL_ENV uv run agent sync push` - Now chunked
- All sync operations

**Risks Identified:**
- **Data Consistency (MEDIUM)**: Partial syncs could leave inconsistent state
- **Performance (LOW)**: Pagination adds overhead but improves scalability
- **Breaking Changes (LOW)**: API remains backward compatible
- **Memory (HIGH - MITIGATED)**: Current implementation fails on large datasets, new implementation fixes this

**Mitigation Strategies:**
- Comprehensive testing with various dataset sizes
- Resume capability for interrupted syncs
- Transaction-like behavior where possible
- Extensive error handling and logging

## Test Strategy

### Unit Tests
Create `tests/sync/test_pagination.py`:
- **`test_pagination_page_sizes`**: Test with page sizes 10, 100, 500, 1000
- **`test_chunking_batch_sizes`**: Test upload chunking with various sizes
- **`test_error_handling_network_timeout`**: Test retry logic for network errors
- **`test_error_handling_api_error`**: Test handling of API errors
- **`test_cursor_edge_cases`**: Test first page, last page, empty results
- **`test_resume_functionality`**: Test resume from interrupted sync

### Integration Tests
Test with actual Supabase instance:
- **Baseline**: Sync with 100 artifacts (verify no regression)
- **Target**: Sync with 1,000 artifacts (primary use case)
- **Stress**: Sync with 10,000 artifacts (scalability test)
- **Network interruption**: Simulate network failure mid-sync, verify resume
- **Partial sync**: Test recovery from partial failures

### Performance Tests
Benchmark and compare:
- **Baseline**: Current implementation with 100 artifacts
- **Target**: New implementation with 1,000 artifacts
- **Memory usage**: Monitor peak memory, verify <500MB for 10K artifacts
- **Sync time**: Measure duration, verify <5 minutes for 1K artifacts
- **Memory leaks**: Run 1-hour sync, verify no memory growth

### Regression Tests
- Verify existing small-dataset syncs unchanged
- Verify sync API backward compatible
- Verify no breaking changes to CLI interface

## User Experience Requirements
- [ ] Display progress: "Syncing artifacts: 234/1000 (23%)"
- [ ] Show estimated time remaining
- [ ] Allow cancellation with Ctrl+C
- [ ] Resume interrupted syncs automatically
- [ ] Display summary: "Synced 1000 artifacts in 2m 34s"

## Observability Requirements
- [ ] Log each page fetch with timing: "Fetched page 5/10 (100 artifacts) in 1.2s"
- [ ] Log memory usage at intervals: "Memory usage: 245MB / 500MB (49%)"
- [ ] Emit metrics: `sync_duration`, `sync_artifact_count`, `sync_memory_peak`
- [ ] Track errors with structured logging
- [ ] Add debug mode for detailed pagination logs (`--debug` flag)

## Documentation Requirements
- [ ] README updated with large dataset guidance
- [ ] Configuration options documented (`AGENT_SYNC_PAGE_SIZE`)
- [ ] Troubleshooting guide for slow syncs
- [ ] CHANGELOG entry for pagination feature
- [ ] Example: "For repos with 1000+ artifacts, set `AGENT_SYNC_PAGE_SIZE=500`"

## Implementation Notes

### Proposed Pagination Strategy
1. **Cursor-based pagination** (recommended for Supabase)
2. **Query structure**: `.range(start, end)` with proper limits
3. **Connection reuse**: Maintain connection across pages
4. **Rate limiting**: Respect Supabase API limits

### File Organization
- Main changes in `agent/sync/sync.py`
- Add `agent/sync/pagination.py` for pagination logic
- Add `agent/sync/progress.py` for progress reporting

### Rollback Plan
If issues are discovered:
1. Revert to non-paginated sync for small datasets
2. Add feature flag to enable/disable pagination
3. Document issues for future attempt

## Governance Panel Notes

**Overall Assessment**: Story enhanced from ~30% to ~90% completeness

**Critical Enhancements Made**:
1. ✅ Added technical specifications (pagination strategy, page sizes, error handling)
2. ✅ Expanded test strategy (unit, integration, performance, regression)
3. ✅ Added UX requirements (progress reporting, resume functionality)
4. ✅ Added observability requirements (logging, metrics, monitoring)
5. ✅ Enhanced acceptance criteria (from 2 to 20+ items)
6. ✅ Defined performance targets (memory usage, sync time, dataset size limits)

**Ready for runbook generation after review.**
