# INFRA-133: Strengthen Agentic Framework Reliability

## State
PROPOSED

## Related Story
INFRA-134, INFRA-135, INFRA-136, INFRA-137

## Summary
The framework's rules have grown excessively large (~70KB across 18 `.agent/rules/` files), leading to context bloat, hallucinated runbook steps, and unintentional feature removals during implementation. Over-reliance on `agent preflight` acts as a delayed, single-point-of-failure safety net that wastes time. This plan shifts validation left by replacing regex-based runbook parsing with Pydantic schemas, moving generic rules into dynamically retrieved context, and adding Langfuse execution tracing to enforce strict scope constraints.

**Predecessor:** INFRA-118 (Squelching Unpredictable Behaviour) — established the I/O validation layer, loop guardrails, and observability foundation that this plan extends.

## Objectives
- **Eliminate Runbook Hallucinations**: Ensure runbooks are 100% sound and machine-executable before they are written to disk, replacing `validate_runbook_schema()` (currently regex-based in `parser.py:152-231`) with strict Pydantic models.
- **Strict Scope Constraint**: Guarantee the agent makes only explicit, requested changes — zero unprompted modifications or feature removals — via Langfuse execution tracing against the source story.
- **De-emphasize Preflight**: Transition from relying on `agent preflight` as a catch-all backstop to utilising upfront, structural validation.
- **Rule Rationalization (Rule Diet)**: Migrate away from overwhelming context windows by moving generic rules from `.agent/rules/` into targeted, retrieved context via NotebookLM and/or Vector DB.

## Milestones

### M1: Shift-Left Validation with Pydantic (INFRA-134)
- **Action**: Deprecate purely free-form markdown generation for runbook creation (`agent runbook`).
- **Implementation**:
  - Define strict `pydantic.BaseModel` schemas: `RunbookStep`, `ModifyBlock`, `SearchReplaceBlock`, `NewBlock`, `DeleteBlock`.
  - Replace the regex-based `validate_runbook_schema()` in `parser.py` with Pydantic validators that intercept and reject malformed `<<<SEARCH>>>` blocks, hallucinated target paths, and syntax errors immediately.
  - Update `runbook.py` to parse AI output into the Pydantic models before writing to disk.
  - Add iterative retry: on `ValidationError`, feed the exact Pydantic error back to the LLM for self-correction (leveraging existing retry patterns from ADR-012 / INFRA-125).
- **Outcome**: The runbook is guaranteed 100% structurally sound before it reaches the implementation phase. Zero tolerance for malformed blocks.
- **Key Files**: `parser.py`, `runbook.py`, `orchestrator.py`

### M2: Dynamic Rule Retrieval — NotebookLM & Vector DB (INFRA-135)
- **Action**: Perform a "Rule Diet". Reduce global prompt files (`GEMINI.md`, `.agent/rules/`, `agents.yaml`) to only absolute core system instructions.
- **Implementation**:
  - Audit and classify the 18 rule files in `.agent/rules/` into **core** (always-included) vs. **contextual** (retrieved on demand).
  - Move contextual rules (architectural patterns, coding standards, role-specific checks) into NotebookLM sources and/or Vector DB.
  - During the "Codebase Introspection" phase in `runbook.py` (lines 221-237), query NotebookLM to dynamically retrieve only the rules directly applicable to the targeted files.
  - Implement a fallback: if retrieval fails, include a static "core governance" schema (`Security`, `QA` minimums) so critical checks are never skipped.
- **Outcome**: Prevents the agent from being confused by conflicting or irrelevant rules, increases focus on the specific task.
- **Key Files**: `runbook.py`, `context.py`, `context_builder.py`, `.agent/rules/*`

### M3: Execution Tracing and Guardrails with Langfuse (INFRA-136)
- **Action**: Implement execution guardrails during the `agent implement` loop.
- **Implementation**:
  - Extend the existing OpenTelemetry tracing in `orchestrator.py` and `implement.py` with Langfuse trace scoring.
  - Trace the agent's reasoning against the initial User Story. On each `apply_chunk()` call, assert that targeted files appear in the Runbook's "Targeted File Contents" section.
  - Introduce a strict "Scope Bounding" check: if an implementation step attempts to touch a file not explicitly approved in the runbook, the action is blocked and logged.
  - Score implementation traces for hallucination rate (schema validation failures from M1) via Langfuse programmatic scoring.
- **Outcome**: Eradicates the possibility of the agent autonomously removing flagship features or making un-asked-for changes.
- **Key Files**: `implement.py`, `orchestrator.py`, `telemetry.py`

### M4: Preflight Rationalization (INFRA-137)
- **Action**: Scale back `agent preflight`.
- **Implementation**:
  - Since Pydantic ensures structure (M1) and Langfuse/VectorDB ensure scope (M3), Preflight becomes a lightweight final verification rather than a heavy, exhaustive capability test.
  - Audit current `check.py` (28KB) and `gates.py` (21KB) to deduplicate checks that are now structurally enforced earlier in the pipeline.
  - Reduce preflight to: lint pass, test pass, and a lightweight schema sanity check.
- **Outcome**: Faster cycle times and less wasted effort.
- **Key Files**: `check.py`, `gates.py`

## Risks & Mitigations
- **Risk**: Moving rules to VectorDB/NotebookLM might lead to missing critical governance checks if retrieval fails.
  - **Mitigation**: Implement a fallback static "core governance" schema that is always included (Security, QA) regardless of retrieval results.
- **Risk**: Pydantic schema coercion might make runbook creation more brittle if the LLM struggles to match the exact schema.
  - **Mitigation**: Use iterative retry (ADR-012 / INFRA-125) to ask the LLM to correct its own JSON/YAML output using the exact Pydantic validation error as feedback.
- **Risk**: Langfuse scope-bounding may block legitimate cross-cutting changes (e.g. updating shared utilities).
  - **Mitigation**: Allow an explicit `cross_cutting: true` annotation in runbook steps to relax scope constraints for documented exceptions.

## Verification
- **Zero-Hallucination Target**: Run `agent implement` with a Pydantic-backed runbook on a complex change; verify 0 parsing errors and 100% `<<<SEARCH/===/>>>` block accuracy.
- **Scope Constraint Test**: Prompt the agent to "refactor the module", and assert that the Langfuse guardrails block any attempts to delete or modify unrelated flagship feature files.
- **Preflight Speed**: Measure preflight execution time to verify a significant reduction due to the architectural shift.
- **Rule Diet Metric**: Measure the token count of context injected into `runbook.py`'s system prompt before and after M2; target ≥50% reduction.

## Copyright

Copyright 2026 Justin Cook
