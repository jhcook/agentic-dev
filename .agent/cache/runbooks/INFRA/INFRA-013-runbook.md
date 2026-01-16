# STORY-ID: INFRA-013: Optimize Sync for Large Datasets

Status: ACCEPTED

## Goal Description

The objective is to enhance the `agent sync` command to handle large datasets (1000+ artifacts) efficiently and reliably by introducing pagination, upload chunking, progress reporting, and resume capability. This will resolve memory issues, improve performance, enhance usability, and maintain strict compliance with API and security requirements.

## Panel Review Findings

### @Architect
- Pagination strategy aligns with industry best practices. Cursor-based pagination ensures scalability and prevents large memory overheads.
- Clear separation of concerns proposed (pagination logic in `agent/sync/pagination.py`, progress logic in `agent/sync/progress.py`).
- The design avoids breaking changes to current workflows by maintaining backward compatibility.
- Suggests articulating edge case behavior like empty datasets and large offsets to ensure smooth operations.

### @Security
- Supabase row-level security policies are respected, reducing the risk of unauthorized access during sync.
- Rate limiting at the user level is essential to mitigate abuse. Validation of cursor tokens is necessary to prevent tampering.
- Exponential backoff and failure thresholds set for retries reduce risks of rate-limiting issues or distributed denial of service impacts.
- Data security issues (like sensitive artifact metadata during sync) are not addressed explicitly. Logging must ensure no sensitive data is exposed.

### @QA
- Comprehensive test strategy provided, but additional tests for malformed cursor values and large gap datasets would strengthen quality.
- Stress and performance tests at scale (e.g., 10,000+ artifacts) highlight memory and time constraints but missing tests for simultaneous concurrent syncs by multiple users.
- Ensure no regression for smaller datasets as part of baseline testing.

### @Docs
- Required updates are clearly outlined (README, CHANGELOG, configuration options, troubleshooting guide).
- Missing explanation of how progress indicators and resume functionality work under the hood.
- Including a "best practices" section for configuring `AGENT_SYNC_PAGE_SIZE` for varied dataset sizes is recommended.

### @Compliance
- No violations identified under `adr-standards.mdc`. Adheres to the principles of immutability and clarity in decisions.
- Conforms to `api-contract-validation.mdc`. No changes to API design result in breaking changes. The OpenAPI specification must be regenerated and updated.
- Recommendation: Log notable discussions or decisions in the ADR for traceability.

### @Observability
- Proposed observability features (structured logging, metrics like `sync_duration`, memory tracking) are comprehensive.
- Debug logging (`--debug` flag) will aid troubleshooting but may add runtime overhead during heavy usage.
- Ensure all logged metadata, such as artifact IDs or page details, avoids PII or sensitive data leaks.

---

## Implementation Steps

### agent/sync/pagination.py
#### NEW file
- Implement reusable pagination logic for cursor-based fetching from Supabase.
- Include argument validations for `start`, `end`, and `page_size`.
- Add a mechanism to retry failed pages with exponential backoff (1s, 2s, 4s).

```python
def fetch_page(cursor, page_size, retries=3):
    for attempt in range(retries):
        try:
            results = supabase
                .from('artifacts')
                .select("*")
                .range(cursor, cursor + page_size - 1)
            return results
        except Exception as e:
            if attempt < retries - 1:
                sleep(2 ** attempt)
            else:
                raise e
```

### agent/sync/progress.py
#### NEW file
- Add progress-tracking utilities.
- Calculate percentage complete and ETA using average time per page.
- Handle user interruptions and save progress state for resumption.

```python
class ProgressTracker:
    def __init__(self, total):
        self.total = total
        self.completed = 0
        self.start_time = time.time()

    def update(self, count):
        self.completed += count
        elapsed = time.time() - self.start_time
        eta = (elapsed / self.completed) * (self.total - self.completed)
        print(f"Progress: {self.completed}/{self.total} ({int(eta)}s remaining)")
```

### agent/sync/sync.py
#### MODIFY
- Integrate new pagination logic and progress tracking.
- Ensure processed pages are cleared from memory to maintain usage under 500MB.
- Store checkpoints after each page to support auto-resume.

```python
from agent.sync.pagination import fetch_page
from agent.sync.progress import ProgressTracker

def sync():
    total = get_total_artifacts()  # Fetch total count from Supabase
    tracker = ProgressTracker(total)
    page_size = os.getenv("AGENT_SYNC_PAGE_SIZE", 100)
    cursor = read_checkpoint() or 0

    while cursor < total:
        try:
            page = fetch_page(cursor, page_size)
            process_page(page)
            cursor += page_size
            tracker.update(len(page))
            save_checkpoint(cursor)
        except KeyboardInterrupt:
            print("Sync interrupted. Saving progress...")
            save_checkpoint(cursor)
            break
```

### agent/core/config.py
#### MODIFY
- Add environment variables for sync page size configuration (`AGENT_SYNC_PAGE_SIZE`, default 100).
- Validate and enforce the maximum limit of 1000.

---

## Verification Plan

### Automated Tests
- [ ] `test_pagination_page_sizes`: Validate pagination with sizes of 10, 100, 500, and 1000.
- [ ] `test_chunking_batch_sizes`: Verify uploads are correctly chunked.
- [ ] `test_error_handling_network_timeout`: Simulate and verify behavior on network errors.
- [ ] `test_resume_functionality`: Simulate interrupted syncs and ensure resumption from the correct checkpoint.

### Manual Verification
- [ ] Sync dataset with 100 artifacts and validate progress reporting.
- [ ] Sync dataset with 10,000 artifacts and monitor memory usage.
- [ ] Simulate network failures mid-sync and verify algorithm handles retries.
- [ ] Run in debug mode and verify detailed logging.

---

## Definition of Done

### Documentation
- [ ] README.md updated with new sync capabilities (`AGENT_SYNC_PAGE_SIZE` usage).
- [ ] CHANGELOG.md entry for pagination and chunking improvements.
- [ ] Troubleshooting guide includes details on handling interruptions.

### Observability
- [ ] Logs include details of fetched pages and memory usage percentages.
- [ ] Metrics for `sync_duration`, `sync_artifact_count`, and `sync_memory_peak` implemented.
- [ ] Debug logs available for detailed troubleshooting.

### Testing
- [ ] All unit, integration, and performance tests pass.
- [ ] Regression cross-validated with small datasets.

---

This story, when fully implemented, will enhance scalability, user experience, and reliability for syncing large datasets.