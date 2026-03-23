# Concurrent Orchestration Design

## Overview
The orchestrator now supports parallel execution of implementation chunks within a single generation phase. This transition from serial to concurrent execution reduces latency for large-scale tasks by overlapping I/O-bound operations.

## Key Mechanisms

**1. Async Task Gathering**
Chunks within a phase are executed using `asyncio.gather`. This allows multiple AI requests and file system modifications to happen simultaneously.

**2. Concurrency Limiting (Semaphore)**
To prevent resource exhaustion (OS file descriptor limits or LLM API rate limits), a `BoundedSemaphore` is used to restrict the number of active concurrent tasks. 
- **Default Limit**: 5 concurrent chunks.
- **Implementation**: Managed within the `Orchestrator` via an internal semaphore used during `apply_chunk_async` calls.

**3. Phase-Gate Integrity**
Parallelism is strictly confined to the *current phase*. The orchestrator ensures all chunks in a phase are resolved (either successful or failed) before evaluating the gate for the next phase. A single permanent chunk failure will halt the entire runbook to preserve system integrity and prevent inconsistent modifications in downstream phases.

## Operational Impact
- **Latency**: Significant reduction in total implementation time for multi-step runbooks.
- **Logs**: Logs are now interleaved. Engineers should rely on the `step_index` and `story_id` fields in structured logs to reconstruct the timeline for a specific chunk.
