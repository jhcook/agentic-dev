# STORY-ID: INFRA-093: Forecast Gate for Runbook Generation

## State

ACCEPTED

## Goal Description

Implement a "Forecast Gate" in the runbook generation workflow to detect oversized or high-complexity stories before they are processed. This prevents AI hallucinations caused by context-stuffing. When a story exceeds defined thresholds (>400 LOC, >8 steps, or >4 files), the system will trigger a decomposition plan instead of a runbook and exit with code 2.

## Linked Journeys

- JRN-064: Forecast-Gated Story Decomposition

## Panel Review Findings

### @Architect
- **ADR Compliance**: Follows ADR-005 (AI-Driven Governance Preflight) by implementing a fail-fast mechanism.
- **Design**: The separation of complexity scoring (heuristic/local) and plan generation (AI-driven) is sound and respects latency requirements.
- **Boundaries**: Logic should reside primarily in `src/agent/commands/runbook.py` but leverage `src/agent/commands/gates.py` for audit logging to maintain consistency with other gate implementations.

### @Qa
- **Test Strategy**: Unit tests for `score_story_complexity` must cover edge cases: empty stories, stories with many checkboxes but few words, and stories with high-intensity verbs.
- **Exit Codes**: Explicitly verify that exit code 2 is returned when the gate triggers. This is critical for CI/CD pipeline integration.

### @Security
- **Audit Logging**: The `--skip-forecast` flag must trigger `log_skip_audit` in `src/agent/commands/gates.py`.
- **Data Privacy**: Ensure the structured logs for `complexity_metrics` do not include story snippets that might contain PII, only the calculated scores.

### @Product
- **UX**: The error message when a story is over-budget should clearly explain *why* it was rejected (e.g., "Step count 12 exceeds limit of 8") and point the user to the generated plan in `.agent/cache/plans/`.
- **Thresholds**: The limits (400 LOC, 8 steps, 4 files) meet current PR size guidelines.

### @Observability
- **Tracing**: Add OpenTelemetry spans for the scoring process.
- **Logs**: Structured logs must include `step_count`, `context_width`, `verb_intensity`, `estimated_loc`, and `gate_decision`.

### @Docs
- **Documentation**: Update the CLI help text for `agent runbook` to include the new `--skip-forecast` flag.
- **Workflow**: Document the "Plan" output format in the internal developer guide.

### @Compliance
- **SOC2**: The audit log for `--skip-forecast` must include the user identity and timestamp.
- **Licensing**: Ensure Apache 2.0 headers are present in new test files.

### @Mobile
- **Constraints**: Not applicable; this is a CLI-based infrastructure task.

### @Web
- **Constraints**: Not applicable; this is a CLI-based infrastructure task.

### @Backend
- **Type Safety**: Use `ComplexityMetrics` dataclass for all scoring passing.
- **Efficiency**: Ensure the heuristic regex is optimized to meet the <100ms performance requirement.

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Convert `print` statements in `src/agent/commands/runbook.py` to `logger.info/error`.
- [ ] Refactor `extract_story_id` in `runbook.py` to a shared utility if it's duplicated elsewhere.

## Implementation Steps

### CLI / Commands

#### [MODIFY] src/agent/commands/runbook.py

- Define a `ComplexityMetrics` dataclass to hold scoring data.
- Implement `score_story_complexity(content: str) -> ComplexityMetrics`:
  - `step_count`: Count lines starting with `- [ ]`.
  - `context_width`: Count links to ADRs (`ADR-XXX`) and Journeys (`JRN-XXX`).
  - `verb_intensity`: Multiplier based on presence of keywords: `refactor` (1.5), `migrate` (2.0), `implement` (1.0).
  - `estimated_loc`: `(step_count * 40) * verb_intensity`.
- Update the `runbook` command signature to include `skip_forecast: bool = typer.Option(False, "--skip-forecast", help="Bypass complexity gate")`.
- Integrate the gate logic before AI runbook generation:

    ```python
    metrics = score_story_complexity(story_content)
    is_over_budget = (metrics.estimated_loc > 400 or 
                      metrics.step_count > 8 or 
                      metrics.file_count > 4)
    
    if is_over_budget and not skip_forecast:
        # Generate Plan
        plan_path = generate_decomposition_plan(story_id, story_content)
        console.print(f"[red]Story exceeds complexity budget.[/red]")
        console.print(f"Plan generated at: {plan_path}")
        raise typer.Exit(code=2)
    
    if skip_forecast:
        from agent.commands.gates import log_skip_audit
        log_skip_audit("runbook_forecast")
    ```

#### [MODIFY] src/agent/commands/gates.py

- Expand `log_skip_audit` signature from `(gate_name: str)` to `(gate_name: str, resource_id: str)` with structured audit dict:

    ```python
    import getpass

    def log_skip_audit(gate_name: str, resource_id: str) -> None:
        """Log a timestamped audit entry when a governance gate is skipped.

        Args:
            gate_name: Human-readable name of the skipped gate.
            resource_id: Identifier for the resource being bypassed (e.g. story ID).
        """
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "user": getpass.getuser(),
            "gate": gate_name,
            "resource": resource_id,
            "action": "BYPASS",
        }
        logger.warning("[AUDIT] gate_bypass %s", audit_entry)
    ```

#### [MODIFY] src/agent/commands/implement.py

- Update the 2 existing callers to pass `story_id` as the new `resource_id` parameter:
  - Line 768: `gates.log_skip_audit("Security scan", story_id)`
  - Line 787: `gates.log_skip_audit("QA tests", story_id)`

#### [NEW] .agent/tests/commands/test_runbook_forecast.py

- Test `score_story_complexity` with various inputs (parametrized boundary tests: exactly 400 LOC, 8 steps, 4 files → PASS).
- Mock the AI call for plan generation and verify the file is created in `.agent/cache/plans/`.
- Verify exit code 2 when limits are exceeded.
- Verify `log_skip_audit` call when `--skip-forecast` is used, asserting `resource_id` and `user` are present in the structured audit entry.
- Verify existing callers in `implement.py` still pass tests after signature change.

## Verification Plan

### Automated Tests
- [ ] `pytest .agent/tests/commands/test_runbook_forecast.py`
- [ ] `pytest .agent/tests/commands/test_implement.py` (verify existing `log_skip_audit` callers still work)
- [ ] `agent runbook --story <OVER_BUDGET_STORY>` returns exit code 2.
- [ ] `agent runbook --story <OVER_BUDGET_STORY> --skip-forecast` proceeds and logs structured audit with `user`, `resource`, `gate`.

### Manual Verification
- [ ] Run `agent runbook` on a known large story and verify the `.agent/cache/plans/STORY-ID-plan.md` exists and contains child story references.
- [ ] Verify structured logs in `logs/agent.log` contain complexity metrics.

## Definition of Done

### Documentation
- [ ] CHANGELOG.md updated with INFRA-093.
- [ ] CLI help updated for `agent runbook`.

### Observability
- [ ] Logs are structured and free of PII.
- [ ] `ComplexityMetrics` span attributes added to OpenTelemetry.

### Testing
- [ ] Unit tests passed.
- [ ] Integration tests for exit codes passed.

## Copyright

Copyright 2026 Justin Cook
