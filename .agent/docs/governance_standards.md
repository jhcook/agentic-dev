# Governance Standards: Code Quality and Complexity (ADR-012)

To ensure the long-term maintainability and modularity of the codebase, the following standards are enforced during the `preflight` and `check` routines.

## Complexity Thresholds

Thresholds are applied deterministically to changed files in a diff before they can be committed or merged.

**1. File Length (LOC)**
- **Threshold**: 500 Lines of Code.
- **Action**: **WARNING**.
- **Rationale**: Files exceeding 500 lines increase cognitive load and maintenance risk. Code should be decomposed into smaller, focused modules.

**2. Function Length**
- **Warning Threshold**: 21–50 lines.
- **Block Threshold**: > 50 lines.
- **Action**: **WARNING** for 21-50, **BLOCK** (Fail) for > 50.
- **Rationale**: Short, focused functions are significantly easier to test and debug. Functions exceeding 50 lines are considered "God Functions" and must be refactored.

## Verification Method

- **Deterministic Check**: Measurements are performed using Python's `ast` module to ensure accuracy by measuring logic lines and excluding leading docstrings or comments from the calculation where applicable.
- **AI Panel Oversight**: Even if hard thresholds are not met, the AI Governance Council reviews all changes for architectural debt and may issue advisory findings.
- **Cross-Validation**: AI-generated syntax claims are cross-referenced against `py_compile` outcomes to eliminate hallucinations.

## Enforcement

These standards are non-negotiable for the core repository. Hard blocks prevent changes from being merged via `agent pr` until the offending code is refactored to meet the standards defined in **ADR-012**.

---
Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0
