# agent new-runbook

Generate a detailed implementation runbook for a committed user story. Starting with version 2.0.0, this command uses a high-performance parallelized generation engine to reduce latency.

## Usage

```bash
agent new-runbook <STORY_ID> [FLAGS]
```

## Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--provider` | auto | Force AI provider (`gemini`, `vertex`, `openai`, `anthropic`, `gh`) |
| `--timeout` | `180` | AI request timeout in seconds |
| `--skip-forecast` | `false` | Bypass the complexity forecast gate |
| `--legacy-gen` | `false` | Use legacy single-pass generation engine (disables chunked v2 engine) |
| `--force` | `false` | Overwrite an existing runbook even if valid |

## Parallel Execution Engine

From v2.0.0, `new-runbook` uses a chunked two-phase pipeline:

1. **Skeleton phase** — AI generates a structured table-of-contents.
2. **Block phase** — Each section is generated in parallel using `TaskExecutor`, respecting a configurable concurrency limit.

This reduces end-to-end generation time from O(N) to approximately O(1) for typical runbook sizes.

Resume support is built in: if generation is interrupted, re-running the command resumes from the last completed block checkpoint (`.partial` file).

## Observability

All parallel task executions are instrumented with OpenTelemetry spans:

- **`task.execute.<idx>`** — One span per parallel block, with `task.index` and `task.status` attributes.
- **`task.failures`** counter — Incremented via `record_task_error` on any block failure.

Set `OTEL_EXPORTER_OTLP_ENDPOINT` to export traces and metrics to your observability backend.

## Token Telemetry

Token usage is tracked via `UsageTracker` and exported through `record_token_usage`:

```python
from observability.token_counter import UsageTracker

tracker = UsageTracker()
tracker.record_call(model="gemini-pro", input_tokens=512, output_tokens=256)
tracker.print_summary()
```

Metrics are published to the `llm.tokens.consumed` OTel counter with `model` and `type` (`input`/`output`) attributes.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `INCOMPLETE IMPLEMENTATION` after `agent implement` | Docstring gate hard-rejected a `[NEW]` file | Upgrade to ≥ v2.0.0 — gate now warns instead of blocking |
| `S/R validation: N auto-corrected (similarity: 65%)` | Fuzzy threshold too low | Raise threshold to `0.80` in `validate_and_correct_sr_blocks` call |
| `Story INFRA-XXX is not COMMITTED` | Story state hasn't been transitioned | Run `agent commit-story INFRA-XXX` or manually edit `## State` |
| Timeout during generation | Large story exceeds default 180s | Pass `--timeout 300` |

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0.
