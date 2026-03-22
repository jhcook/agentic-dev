# ADR-045: Chunked Runbook Generation Pipeline

## Status

ACCEPTED

## Date

2026-03-22

## Context

Single-pass AI generation of large runbooks exceeds context windows and produces
lower-quality output for complex stories with many implementation steps. The AI
struggles to maintain consistency across 10+ sections in a single prompt.

## Decision

Implement a two-phase chunked generation pipeline:

1. **Phase 1 — Skeleton Generation**: AI produces a JSON table-of-contents with
   section titles, descriptions, and expected file changes.
2. **Phase 2 — Block Generation**: Each section is generated independently with
   full context from the skeleton, story, and prior section summaries.

### Model Separation

Generation-domain models (`GenerationSkeleton`, `GenerationSection`,
`GenerationBlock`) in `runbook_generation.py` are deliberately separate from
parser-domain models (`RunbookSkeleton`, `RunbookBlock`) in `chunk_models.py`.

- **Generation models** represent the AI's structured JSON output (title, sections,
  descriptions).
- **Parser models** represent addressable document blocks with whitespace
  preservation (id, content, prefix/suffix whitespace).

## Consequences

- Generation can be parallelised per-section in future.
- Prior-change tracking prevents duplicate code blocks across sections.
- Model separation avoids coupling generation lifecycle to parser lifecycle.
- Two AI calls per section increases latency but improves quality.

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0.
