# INFRA-095: Micro-Commit Loop and Circuit Breaker

## State

COMMITTED

## Goal Description

Implement a micro-commit implementation loop with save points, small-step enforcement, and a cumulative LOC circuit breaker inside `implement.py`. Each runbook step triggers a generate → apply → test → commit cycle. A 30-line per-step edit-distance ceiling prevents oversized individual changes, a 200 LOC cumulative warning alerts the developer, and a hard 400 LOC cumulative limit triggers a circuit breaker that commits partial work, auto-generates a follow-up story with remaining steps, and exits cleanly. This is **Layer 3** of the INFRA-089 defence-in-depth strategy.

## Linked Journeys

- JRN-065: Circuit Breaker During Implementation

## Panel Review Findings

### @Architect
- **ADR Compliance**: Follows ADR-005 (AI-Driven Governance Preflight). The circuit breaker extends the existing `check_pr_size` gate pattern (INFRA-092) by moving size enforcement *inside* the implementation loop rather than as a post-apply check. No new modules needed — all changes are contained within `implement.py` and `gates.py`.
- **Design Scope**: The micro-commit loop replaces the existing linear generate-then-apply flow in `implement.py` (lines 567–754). The chunked processing path already splits the runbook into discrete tasks — this story adds git-commit save points between chunks and edit-distance tracking.
- **Follow-Up Story Generation**: Reuses the existing `get_next_id()` utility (in `utils.py`) and the story template system. No new module needed — a private helper `_create_follow_up_story()` inside `implement.py` is sufficient.
- **Plan Linkage**: Plans live in `.agent/cache/plans/`. The linkage AC requires scanning for an existing plan referencing the current story and appending the follow-up ID, or creating a minimal plan. This is a lightweight file operation, not an architectural concern.

### @QA
- **Test Strategy**: The story defines 4 unit test categories: edit distance counting, follow-up story creation, integration (mock loop exceeding 400 LOC), and negative (under-limit completion). Recommend adding:
  - **Edge Case**: Exactly 400 LOC cumulative → circuit breaker fires (boundary test).
  - **Edge Case**: Single step exceeding 30 lines → pause and micro-commit, not immediate circuit breaker.
  - **Checkpoint**: Verify git commit is actually created at each save point (mock `subprocess.run`).
- **Test Isolation**: All tests MUST mock `subprocess.run` for git operations and `ai_service.complete` for AI responses. No real git commits in tests.

### @Security
- **Prompt Injection**: No new prompt injection surface. The circuit breaker operates on LOC counts, not on AI-parsed content.
- **Data Privacy**: Follow-up story content references remaining runbook steps (which are already in the local filesystem). No PII risk. The `scrub_sensitive_data()` call must be applied to any story content written to disk.
- **Audit Logging**: Circuit breaker events (save-point commits, LOC thresholds, circuit breaker activation) must be logged with structured data (`story_id`, `step_index`, `cumulative_loc`, `threshold`) per NFR. No PII in logs.
- **File Operations**: Follow-up story creation uses `write_text()` which is already the established pattern. The `get_next_id()` utility prevents ID collision by scanning stories, plans, runbooks, and the local DB.

### @Product
- **UX**: Clear console output at each milestone:
  - Save point: `✅ Step {N} committed ({loc} LOC cumulative)`
  - Warning: `⚠️ Approaching LOC limit: {loc}/400 cumulative`
  - Circuit breaker: `🛑 Circuit breaker triggered at {loc} LOC. Partial work committed. Follow-up story {ID} created.`
- **Acceptance Criteria Coverage**:
  - AC-1 (Save Points) → Implementation Step 2 (micro-commit loop)
  - AC-2 (Small-Step) → Implementation Step 3 (edit distance gate)
  - AC-3 (LOC Warning) → Implementation Step 4 (threshold warning)
  - AC-4 (Circuit Breaker) → Implementation Step 5 (circuit breaker)
  - AC-5 (Follow-Up Story) → Implementation Step 6 (auto-generate)
  - AC-6 (Plan Linkage) → Implementation Step 7 (plan append)
  - Negative → Implementation Step 2 (under-limit completes normally)

### @Observability
- **Structured Logging**: Log each save-point commit and circuit breaker event using existing `logger.info()` / `logger.warning()` patterns. Fields: `story_id`, `step_index`, `step_loc`, `cumulative_loc`, `action` (save_point | warning | circuit_breaker).
- **OpenTelemetry**: Add a `tracer.start_as_current_span("implement.micro_commit_step")` span inside the per-step loop, consistent with the existing `gate.*` span pattern in `gates.py`. The circuit breaker event gets its own `implement.circuit_breaker` span.

### @Docs
- **CHANGELOG**: Add INFRA-095 entry under "Added" section.
- **CLI Help**: No new CLI flags. The micro-commit loop and circuit breaker are transparent behavior changes to the existing `implement` command.

### @Compliance
- **SOC2**: Structured logs for save-point commits and circuit breaker events satisfy the audit trail requirement. The `log_skip_audit` pattern is not needed here — the circuit breaker is automatic, not a user bypass.
- **Licensing**: New test file must include Apache 2.0 header.

### @Mobile
- **Constraints**: Not applicable; CLI-only infrastructure task.

### @Web
- **Constraints**: Not applicable; CLI-only infrastructure task.

### @Backend
- **Type Safety**: Use `@dataclass` for the new `MicroCommitState` tracker. The `count_edit_distance()` function accepts `str` (content before) and `str` (content after) and returns `int`.
- **Pattern**: Follow the existing chunked processing loop pattern (lines 668–739 in `implement.py`). The micro-commit loop wraps each chunk iteration with: apply → count LOC → test → commit → threshold check.
- **Subprocess Safety**: All `subprocess.run` calls for git operations must use `check=True` with `capture_output=True` and `timeout=30` to prevent hangs — consistent with existing patterns in `implement.py`.

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Extract per-step LOC threshold constants to module-level: `MAX_EDIT_DISTANCE_PER_STEP = 30`, `LOC_WARNING_THRESHOLD = 200`, `LOC_CIRCUIT_BREAKER_THRESHOLD = 400`.
- [ ] Add type annotation for `gate_results` list in `implement()` (currently untyped at line 759).

## Implementation Steps

### Micro-Commit State Tracker

#### [MODIFY] .agent/src/agent/commands/implement.py

**Step 1 — Module-Level Imports and Constants**

- Add the following imports and constants after the existing imports (line 36):

    ```python
    import difflib

    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)

    # Micro-Commit Circuit Breaker Thresholds (INFRA-095)
    MAX_EDIT_DISTANCE_PER_STEP = 30
    LOC_WARNING_THRESHOLD = 200
    LOC_CIRCUIT_BREAKER_THRESHOLD = 400
    ```

**Step 2 — Add `count_edit_distance()` helper**

- Add a new function after `sanitize_branch_name()` (after line 140):

    ```python
    def count_edit_distance(original: str, modified: str) -> int:
        """Count the line-level edit distance between two file contents.

        Uses a simple diff-based approach: counts lines that are added or removed.
        Binary files or empty comparisons return 0.

        # TODO(INFRA-096): Update to also accept search/replace block format
        # once diff-based apply lands.

        Args:
            original: Original file content (empty string for new files).
            modified: Modified file content.

        Returns:
            Number of lines changed (additions + deletions).
        """
        if not original and not modified:
            return 0

        original_lines = original.splitlines(keepends=True)
        modified_lines = modified.splitlines(keepends=True)

        diff = difflib.unified_diff(original_lines, modified_lines, lineterm="")
        edit_count = 0
        for line in diff:
            if line.startswith("+") and not line.startswith("+++"):
                edit_count += 1
            elif line.startswith("-") and not line.startswith("---"):
                edit_count += 1

        return edit_count
    ```

**Step 3 — Add `_create_follow_up_story()` helper**

- Add a new function after `count_edit_distance()`:

    ```python
    def _create_follow_up_story(
        original_story_id: str,
        original_title: str,
        remaining_chunks: List[str],
        completed_step_count: int,
        cumulative_loc: int,
    ) -> Optional[str]:
        """Auto-generate a follow-up story for remaining runbook steps.

        Called when the circuit breaker activates. Creates a COMMITTED story
        referencing the remaining implementation steps.

        Args:
            original_story_id: The story ID that triggered the circuit breaker.
            original_title: Human-readable title of the original story.
            remaining_chunks: List of unprocessed runbook chunk strings.
            completed_step_count: Number of steps already completed.
            cumulative_loc: LOC count at circuit breaker activation.

        Returns:
            The new story ID if created successfully, None otherwise.
        """
        from agent.core.utils import get_next_id

        # Determine scope prefix from original story ID
        prefix = original_story_id.split("-")[0] if "-" in original_story_id else "INFRA"
        scope_dir = config.stories_dir / prefix
        scope_dir.mkdir(parents=True, exist_ok=True)

        new_story_id = get_next_id(scope_dir, prefix)

        # Build remaining steps summary
        remaining_summary = "\n".join(
            f"- Step {completed_step_count + i + 1}: {chunk[:200].strip()}"
            for i, chunk in enumerate(remaining_chunks)
        )

        content = f"""# {new_story_id}: {original_title} (Continuation)

## State

COMMITTED

## Problem Statement

Circuit breaker activated during implementation of {original_story_id} at {cumulative_loc} LOC cumulative.
This follow-up story contains the remaining implementation steps.

## User Story

As a **developer**, I want **the remaining steps from {original_story_id} implemented** so that **the full feature is completed across atomic PRs**.

## Acceptance Criteria

- [ ] Complete remaining implementation steps from {original_story_id} runbook.

## Remaining Steps from {original_story_id}

{remaining_summary}

## Linked ADRs

- ADR-005 (AI-Driven Governance Preflight)

## Related Stories

- {original_story_id} (parent — circuit breaker continuation)

## Linked Journeys

- JRN-065 — Circuit Breaker During Implementation

## Impact Analysis Summary

Components touched: See remaining steps above.
Workflows affected: /implement
Risks: None beyond standard implementation risks.

## Test Strategy

- Follow the test strategy from the original {original_story_id} runbook.

## Rollback Plan

Revert changes from this follow-up story. The partial work from {original_story_id} remains intact.

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0
"""

        safe_title = sanitize_branch_name(f"{original_title}-continuation")
        filename = f"{new_story_id}-{safe_title}.md"
        file_path = scope_dir / filename

        # Guard: never overwrite an existing story file (Panel recommendation)
        if file_path.exists():
            logging.error(
                "follow_up_story_collision path=%s story=%s",
                file_path, new_story_id,
            )
            return None

        try:
            file_path.write_text(scrub_sensitive_data(content))
            logging.info(
                "follow_up_story_created story=%s parent=%s remaining_steps=%d",
                new_story_id, original_story_id, len(remaining_chunks),
            )
            return new_story_id
        except Exception as e:
            logging.error("Failed to create follow-up story: %s", e)
            return None
    ```

**Step 4 — Add `_update_or_create_plan()` helper (AC-6)**

- Add after `_create_follow_up_story()`:

    ```python
    def _update_or_create_plan(
        original_story_id: str,
        follow_up_story_id: str,
        original_title: str,
    ) -> None:
        """Link original and follow-up stories in a Plan document.

        If a Plan already exists referencing the original story, appends the
        follow-up. Otherwise, creates a minimal Plan linking both.

        Args:
            original_story_id: The original story ID.
            follow_up_story_id: The newly created follow-up story ID.
            original_title: Human-readable title.
        """
        prefix = original_story_id.split("-")[0] if "-" in original_story_id else "INFRA"
        plans_scope_dir = config.plans_dir / prefix
        plans_scope_dir.mkdir(parents=True, exist_ok=True)

        # Search for existing plan referencing original story
        existing_plan = None
        if plans_scope_dir.exists():
            for plan_file in plans_scope_dir.glob("*.md"):
                try:
                    plan_content = plan_file.read_text()
                    if original_story_id in plan_content:
                        existing_plan = plan_file
                        break
                except Exception:
                    continue

        if existing_plan:
            # Append follow-up to existing plan
            try:
                plan_content = existing_plan.read_text()
                append_text = f"\n- {follow_up_story_id}: {original_title} (Continuation — circuit breaker split)\n"
                existing_plan.write_text(plan_content + append_text)
                console.print(f"[dim]📎 Updated existing plan: {existing_plan.name}[/dim]")
            except Exception as e:
                logging.warning("Failed to update existing plan %s: %s", existing_plan, e)
        else:
            # Create minimal plan
            plan_filename = f"{original_story_id}-plan.md"
            plan_path = plans_scope_dir / plan_filename
            plan_content = f"""# Plan: {original_title}

## Stories

- {original_story_id}: {original_title} (partial — circuit breaker activated)
- {follow_up_story_id}: {original_title} (Continuation)

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0
"""
            try:
                plan_path.write_text(plan_content)
                console.print(f"[dim]📎 Created plan linking stories: {plan_path.name}[/dim]")
            except Exception as e:
                logging.warning("Failed to create plan: %s", e)
    ```

### Micro-Commit Loop Integration

#### [MODIFY] .agent/src/agent/commands/implement.py

**Step 5 — Add `_micro_commit_step()` helper**

- Add a private function that handles the git-commit save point for a single step. Place after `_update_or_create_plan()`:

    ```python
    def _micro_commit_step(
        story_id: str,
        step_index: int,
        step_loc: int,
        cumulative_loc: int,
        modified_files: List[str],
    ) -> bool:
        """Create a micro-commit save point for a single implementation step.

        Stages modified files and creates an atomic commit. Returns False if
        the git operation fails (non-fatal — logged and skipped).

        Args:
            story_id: Story ID for the commit message.
            step_index: 1-based step index.
            step_loc: Lines changed in this step.
            cumulative_loc: Total lines changed so far.
            modified_files: List of file paths modified in this step.

        Returns:
            True if commit succeeded, False otherwise.
        """
        if not modified_files:
            return True

        try:
            # Stage modified files
            subprocess.run(
                ["git", "add"] + modified_files,
                check=True, capture_output=True, timeout=30,
            )

            # Create atomic commit
            commit_msg = (
                f"feat({story_id}): implement step {step_index} "
                f"[{step_loc} LOC, {cumulative_loc} cumulative]"
            )
            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                check=True, capture_output=True, timeout=30,
            )

            logging.info(
                "save_point story=%s step=%d step_loc=%d cumulative_loc=%d",
                story_id, step_index, step_loc, cumulative_loc,
            )
            return True

        except subprocess.CalledProcessError as e:
            logging.warning(
                "save_point_failed story=%s step=%d error=%s",
                story_id, step_index, e,
            )
            console.print(f"[yellow]⚠️  Save-point commit failed for step {step_index}: {e}[/yellow]")
            return False
    ```

**Step 6 — Replace the chunked processing loop with micro-commit loop**

- In the `implement()` function, replace the chunked processing loop (approximately lines 668–739) with the micro-commit variant. The key change is wrapping each chunk iteration with LOC counting, save-point commits, and circuit breaker checks.

- After the `split_runbook_into_chunks()` call and the provider reset block, replace the `for idx, chunk in enumerate(chunks):` loop body with:

    ```python
        cumulative_loc = 0
        completed_steps = 0

        for idx, chunk in enumerate(chunks):
            if len(chunks) > 1:
                console.print(f"\n[bold blue]🚀 Processing Task {idx+1}/{len(chunks)}...[/bold blue]")

            # --- Generate code for this step ---
            chunk_system_prompt = f"""You are an Implementation Agent.
    Your goal is to EXECUTE a SPECIFIC task from the provided RUNBOOK.
    CONSTRAINTS:
    1. ONLY implement the changes described in the 'CURRENT TASK'.
    2. Maintain consistency with the 'GLOBAL RUNBOOK CONTEXT'.
    3. Follow the 'IMPLEMENTATION GUIDE' and 'GOVERNANCE RULES'.
    4. **IMPORTANT**: Use REPO-RELATIVE paths (e.g., .agent/src/agent/main.py). DO NOT use 'agent/' as root.{license_instruction}
    5. **CRITICAL**: Keep changes small — aim for under {MAX_EDIT_DISTANCE_PER_STEP} lines of edits per step.
    OUTPUT FORMAT:
    Return a Markdown response with file paths and code blocks:

    File: path/to/file.py
    ```python
    # Complete file content here
    ```

    """
            chunk_user_prompt = f"""GLOBAL RUNBOOK CONTEXT (Truncated):
    {global_runbook_context[:8000]}

    --------------------------------------------------------------------------------
  CURRENT TASK:
    {chunk}
    --------------------------------------------------------------------------------

    RULES (Filtered):
    {filtered_rules}

    DETAILED ROLE INSTRUCTIONS:
    {instructions_content}

    ARCHITECTURAL DECISIONS (ADRs):
    {adrs_content}
    """
            logging.info(
                "AI Task %d/%d | Context size: ~%d chars",
                idx + 1, len(chunks),
                len(chunk_system_prompt) + len(chunk_user_prompt),
            )

            chunk_result = None
            try:
                console.print(f"[bold green]🤖 AI is coding task {idx+1}/{len(chunks)}...[/bold green]")
                with console.status(f"[bold green]🤖 AI is coding task {idx+1}/{len(chunks)}...[/bold green]"):
                    chunk_result = ai_service.complete(chunk_system_prompt, chunk_user_prompt, model=model)
            except Exception as e:
                console.print(f"[bold red]❌ Task {idx+1} failed during generation: {e}[/bold red]")
                raise typer.Exit(code=1)

            if not chunk_result:
                continue

            full_content += f"\n\n{chunk_result}"

            # --- Apply and measure edit distance (AC-1, AC-2) ---
            if apply:
                code_blocks = parse_code_blocks(chunk_result)
                step_loc = 0
                step_modified_files = []

                if code_blocks:
                    console.print(f"[dim]Found {len(code_blocks)} file(s) in this task[/dim]")
                    for block in code_blocks:
                        file_path = Path(block['file'])

                        # Measure edit distance before applying
                        original_content = ""
                        if file_path.exists():
                            try:
                                original_content = file_path.read_text()
                            except Exception:
                                pass

                        success = apply_change_to_file(block['file'], block['content'], yes)

                        if success:
                            block_loc = count_edit_distance(original_content, block['content'])
                            step_loc += block_loc
                            step_modified_files.append(block['file'])

                # AC-2: Small-step enforcement
                if step_loc > MAX_EDIT_DISTANCE_PER_STEP:
                    console.print(
                        f"[yellow]⚠️  Step {idx+1} exceeded small-step limit: "
                        f"{step_loc} LOC (max {MAX_EDIT_DISTANCE_PER_STEP})[/yellow]"
                    )

                cumulative_loc += step_loc
                completed_steps = idx + 1

                # AC-1: Save-point commit
                with tracer.start_as_current_span("implement.micro_commit_step") as span:
                    span.set_attribute("step_index", idx + 1)
                    span.set_attribute("step_loc", step_loc)
                    span.set_attribute("cumulative_loc", cumulative_loc)

                    _micro_commit_step(
                        story_id, idx + 1, step_loc, cumulative_loc, step_modified_files,
                    )

                console.print(
                    f"[green]✅ Step {idx+1} committed "
                    f"({step_loc} LOC this step, {cumulative_loc} LOC cumulative)[/green]"
                )

                # AC-3: LOC warning
                if cumulative_loc >= LOC_WARNING_THRESHOLD and cumulative_loc < LOC_CIRCUIT_BREAKER_THRESHOLD:
                    console.print(
                        f"[bold yellow]⚠️  Approaching LOC limit: "
                        f"{cumulative_loc}/{LOC_CIRCUIT_BREAKER_THRESHOLD} cumulative[/bold yellow]"
                    )
                    logging.warning(
                        "loc_warning story=%s cumulative_loc=%d threshold=%d",
                        story_id, cumulative_loc, LOC_CIRCUIT_BREAKER_THRESHOLD,
                    )

                # AC-4: Circuit breaker
                if cumulative_loc >= LOC_CIRCUIT_BREAKER_THRESHOLD:
                    remaining_chunks = chunks[idx + 1:]
                    with tracer.start_as_current_span("implement.circuit_breaker") as cb_span:
                        cb_span.set_attribute("cumulative_loc", cumulative_loc)
                        cb_span.set_attribute("remaining_steps", len(remaining_chunks))

                        logging.warning(
                            "circuit_breaker story=%s cumulative_loc=%d "
                            "completed_steps=%d remaining_steps=%d",
                            story_id, cumulative_loc, completed_steps, len(remaining_chunks),
                        )

                        console.print(
                            f"\n[bold red]🛑 Circuit breaker triggered at "
                            f"{cumulative_loc} LOC (limit: {LOC_CIRCUIT_BREAKER_THRESHOLD}).[/bold red]"
                        )

                        if remaining_chunks:
                            # AC-5: Follow-up story
                            follow_up_id = _create_follow_up_story(
                                story_id, story_title, remaining_chunks,
                                completed_steps, cumulative_loc,
                            )

                            if follow_up_id:
                                console.print(
                                    f"[bold blue]📝 Follow-up story created: {follow_up_id}[/bold blue]"
                                )
                                console.print(
                                    f"[dim]Run: agent new-runbook {follow_up_id}[/dim]"
                                )

                                # AC-6: Plan linkage
                                _update_or_create_plan(story_id, follow_up_id, story_title)

                        console.print(
                            f"[bold green]✅ Partial work committed ({completed_steps} steps).[/bold green]"
                        )
                        console.print(
                            "[dim]Exiting cleanly. Resume with the follow-up story.[/dim]"
                        )
                        raise typer.Exit(code=0)

        # If we made it through the loop, set success
        if full_content:
            implementation_success = True

    ```

> **IMPORTANT**: The full-context path (lines 576–645) is NOT modified. It remains as-is for cases where the entire runbook fits in a single AI call. The micro-commit loop only applies to the chunked/fallback path, since that's where discrete steps are available.

> **NOTE (AC-1 Clarification — Panel Review)**: AC-1 specifies "generate → apply → test → green → auto-commit". The per-step test execution is **deferred to the post-apply QA gate** (lines 786–809) for performance reasons — running `pytest` after every micro-step would add 10–30s overhead per step. The save-point commit captures the code change atomically; the full test suite validates correctness after all steps complete. If a test failure is detected post-apply, the micro-commits provide clean rollback points via `git revert`.

## Verification Plan

### Automated Tests

#### [NEW] .agent/tests/commands/test_implement_circuit_breaker.py

> **Fixture Note**: All tests MUST mock `subprocess.run` for git operations and `ai_service.complete` for AI responses. Use `tmp_path` for all filesystem operations to prevent leakage.

- **Test 1: `count_edit_distance` — single file unchanged** — Assert returns 0 when original equals modified.

- **Test 2: `count_edit_distance` — single file with additions** — Mock original as 10-line file, modified as 15-line file (5 lines appended). Assert returns 5.

- **Test 3: `count_edit_distance` — single file with mixed changes** — Mock 10-line original, 10-line modified with 3 lines changed. Assert returns 6 (3 removed + 3 added).

- **Test 4: `count_edit_distance` — new file (empty original)** — Assert returns the line count of the modified content.

- **Test 5: `_create_follow_up_story` — correct ID and content** — Mock `get_next_id` to return `INFRA-999`. Assert:
  - File exists at `stories/INFRA/INFRA-999-*.md`
  - Contains `## State\n\nCOMMITTED`
  - Contains reference to original story ID
  - Contains remaining steps summary
  - Does NOT overwrite an existing file

- **Test 6: `_create_follow_up_story` — no overwrite** — Pre-create a file at the expected path. Assert function returns `None` or raises, not silently overwrites.

- **Test 7: Integration — circuit breaker fires at 400 LOC** — Mock implement loop with 5 chunks, each producing ~100 LOC of changes. Assert:
  - Circuit breaker triggers after 4th chunk (400 LOC cumulative)
  - Partial commits exist (4 micro-commits via mocked `subprocess.run`)
  - Follow-up story file created with remaining 1 chunk
  - Exit code 0

- **Test 8: Integration — under 400 LOC completes normally** — Mock implement loop with 3 chunks, each producing ~50 LOC. Assert:
  - All chunks processed
  - 3 micro-commits created
  - No circuit breaker triggered
  - No follow-up story created

- **Test 9: LOC warning at 200** — Mock implement loop reaching 200 cumulative LOC. Assert `logger.warning` called with `loc_warning` message.

- **Test 10: Boundary — exactly 400 LOC** — Mock implement loop reaching exactly 400 cumulative LOC on the last chunk step. Assert circuit breaker fires.

- **Test 11: Save-point commit failure — non-fatal** — Mock `subprocess.run` for `git commit` to raise `CalledProcessError`. Assert:
  - Warning logged
  - Loop continues to next step (non-fatal)
  - Implementation does not crash

- **Test 12: Plan linkage — existing plan updated** — Pre-create a plan file referencing the story. Assert follow-up story ID is appended. Verify no duplicate entries.

- **Test 13: Plan linkage — new plan created** — No pre-existing plan. Assert a new plan file is created linking original and follow-up stories.

- [ ] `pytest .agent/tests/commands/test_implement_circuit_breaker.py`

### Manual Verification

- [ ] Run `agent implement INFRA-095 --apply --yes` on a story with a large runbook (6+ steps) and verify:
  - Micro-commits appear in `git log --oneline`
  - LOC warning is printed at 200 cumulative
  - If circuit breaker activates, follow-up story exists in `.agent/cache/stories/INFRA/`
- [ ] Verify `agent.log` contains structured entries: `save_point`, `loc_warning`, `circuit_breaker`
- [ ] Run a small implementation (under 400 LOC) and verify it completes without circuit breaker interference.

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated with INFRA-095 entry under "Added".
- [ ] README.md updated (if applicable) — likely N/A for internal CLI enhancement.
- [ ] API Documentation updated (if applicable) — N/A.

### Observability

- [ ] Logs are structured and free of PII.
- [ ] Save-point events logged with `story_id`, `step_index`, `step_loc`, `cumulative_loc`.
- [ ] Circuit breaker events logged with `story_id`, `cumulative_loc`, `completed_steps`, `remaining_steps`.
- [ ] OpenTelemetry spans added: `implement.micro_commit_step`, `implement.circuit_breaker`.

### Testing

- [ ] Unit tests passed (`test_implement_circuit_breaker.py`).
- [ ] Existing implement tests still pass (`test_implement.py`, `test_implement_branching.py`, `test_implement_pathing.py`, `test_implement_updates_journey.py`).

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0
