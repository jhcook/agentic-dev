# Architecture: Two-Pass Runbook Generation

This document outlines the architecture for Phase 2b of the runbook generation pipeline, designed to solve the problem of "imagined APIs" during test code generation.

**The Coherence Problem**

Previously, all runbook sections were generated in parallel. This meant the AI generating tests had no visibility into the function signatures, return types, or directory structures created by the implementation sections in the same runbook. This led to high failure rates during governance preflight checks.

**Two-Pass Execution Sequence**

The pipeline now executes Phase 2b in two distinct sequential batches:

1. **Pass 1: Implementation Blocks**: All sections classified as implementation logic are generated in parallel. The resulting code blocks are captured and mapped to their target file paths.
2. **Pass 2: Verification Blocks**: All sections classified as verification or testing logic are generated in parallel. Crucially, the code generated in Pass 1 is injected into these prompts as `implementation_context`.

**Classification Engine**

The `runbook_generation.py` module uses a heuristic-based classification engine to assign sections to either Pass 1 or Pass 2. 

**Verification Heuristics:**
- **Title Heuristic**: If a section title contains keywords such as 'Test', 'Verification', 'Validation', 'QA', or 'Suite'.
- **File Heuristic**: If a section's file list includes any path matching the pattern `test_*.py` or containing a `tests/` directory.

**Implementation Heuristics:**
- All sections that do not meet the Verification criteria (e.g., 'Architecture Review', 'Core Logic', 'Documentation', 'Security').

**Annotating Runbook Skeletons**

For complex stories requiring high-fidelity tests, ensure the following during skeleton generation:
- **Clear Separation**: Do not mix implementation files (e.g., `src/...`) and test files (e.g., `tests/...`) in the same section.
- **Standard Naming**: Use titles like 'Verification & Test Suite' to ensure the classification engine correctly identifies the section for Pass 2 execution.

## Copyright

Copyright 2026 Justin Cook
