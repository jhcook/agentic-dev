# Retry Logic and Error States

## Retry Strategy
The implementation engine utilizes a granular, per-chunk retry strategy. This ensures that transient network errors or temporary file system locks do not cause the entire implementation process to fail.

**Configuration Parameters**
The following parameters are defined in `agent.core.implement.retry` and applied via the `retry_with_backoff` decorator:

| Parameter | Default | Description |
| :--- | :--- | :--- |
| `max_retries` | 3 | Number of attempts after the initial failure. |
| `base_delay` | 1.0s | Initial wait time before the first retry. |
| `max_delay` | 30.0s | Upper bound for exponential backoff delay. |
| `backoff_factor` | 2.0 | Multiplier for the delay after each failure. |
| `jitter` | True | Adds random variance (Full Jitter) to prevent synchronized retries. |

## Error Definitions for Engineers

**MaxRetriesExceededError**
Raised when a chunk-level task fails more than `max_retries` times. This error is terminal for the specific implementation task and bubbles up to the orchestrator.

**Failure Propagation & State**
1. **Chunk Failure**: If a chunk fails all retries, it raises `MaxRetriesExceededError`.
2. **Phase Halt**: The orchestrator catches this error, stops processing any remaining tasks in the queue, and marks the story as `FAILED`.
3. **State Preservation**: Successful chunks from the same or previous phases are *not* rolled back. This allows engineers to inspect partial successes and manually intervene or resume from a known state.

## Observability
Engineers should monitor the `agent.core.implement.telemetry` logger for the following events:
- `chunk_retry`: Emitted when a transient error triggers a retry attempt.
- `chunk_failure`: Emitted when a chunk reaches the retry limit.
- `retry_count`: Metadata field providing the attempt sequence (1, 2, 3).


## Copyright

Copyright 2026 Justin Cook
