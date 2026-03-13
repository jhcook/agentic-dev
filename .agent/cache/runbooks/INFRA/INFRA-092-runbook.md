# STORY-ID: INFRA-092: Post-Apply PR Size Gate

## State

COMMITTED

## Goal Description

Implement an automated PR size gate within the `agent implement` workflow to enforce a 400-line-of-code (LOC) limit on staged changes. This serves as a "circuit breaker" to prevent context stuffing and hallucinations in AI governance checks (Layer 5 of the INFRA-089 defense-in-depth strategy). The gate includes specific exemptions for automated chores, refactors, net-negative changes (more deletions than additions), and non-code assets.

## Linked Journeys

- JRN-065: Circuit Breaker During Implementation
- JRN-057: Impact Analysis Workflow

## Panel Review Findings

### @Architect
- The placement of the gate in `gates.py` using the existing `GateResult` pattern is compliant with ADR-005.
- Ensuring the gate runs *post-apply* but *pre-governance* is critical to ensure the AI "Council" isn't overwhelmed by large diffs.

### @Qa
- Test strategy must cover all edge cases: exactly 400 LOC (pass), 401 LOC (fail), 1000 lines deleted / 200 added (pass - net negative), and the specific prefix bypasses.
- Need to mock `subprocess.run` to simulate `git diff --cached --numstat` outputs.

### @Security
- No PII or file contents should be logged. The `check_pr_size` function must only log aggregate counts (`total_additions`, `total_deletions`) and the final decision.
- Ensure the shell command execution is safe (no shell injection via filenames).

### @Product
- The 400 LOC limit is a sensible default for AI-augmented development.
- The rejection message should clearly explain *why* it failed and how to bypass (e.g., split the PR or use the allowed prefixes if appropriate).

### @Observability
- Use the existing OpenTelemetry tracer in `gates.py`.
- Log structured events for every gate execution to track "PR Friction" metrics.

### @Docs
- Update `CHANGELOG.md` to reflect the new governance gate.
- No changes required to user-facing README at this stage as this is an internal framework enforcement.

### @Compliance
- Ensure Apache 2.0 license headers are on new test files.
- No GDPR implications as we are processing file metadata (line counts), not PII.

### @Mobile
- Ensure asset files common in Expo/React Native projects (e.g., `.expo`, `.json`, `.png`) are correctly excluded in the filter list to avoid blocking legitimate asset-heavy PRs.

### @Web
- Ensure `.svg` and `.json` (translations/configs) are excluded to prevent large UI asset updates from triggering the gate.

### @Backend
- Implementation must use strict typing for `GateResult`.
- Use `git diff --cached --numstat` for accurate, machine-readable diff statistics.

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Convert any raw `print` statements in `src/agent/commands/gates.py` to use the structured `logger`.
- [ ] Align `check_commit_size` and the new `check_pr_size` to share a common helper for parsing git numstat if applicable.

## Implementation Steps

### Backend Infrastructure (Governance Gates)

#### MODIFY src/agent/commands/gates.py

- Import `re` and `trace` (if not already used).
- Implement `check_pr_size(threshold: int = 400, commit_message: Optional[str] = None) -> GateResult`.
- Logic for LOC Calculation:
    1. Run `git diff --cached --numstat`.
    2. Parse output: `additions`, `deletions`, `filepath`.
    3. Filter out files ending in: `.json`, `.yaml`, `.yml`, `.png`, `.jpg`, `.jpeg`, `.svg`, `.lock`, `.md`, `.txt`.
    4. Calculate `total_additions` and `total_deletions`.
- Logic for Exemptions:
    1. **Net-Negative**: If `total_deletions > total_additions`, return `GateResult(passed=True)`.
    2. **Prefix Bypass**: If `commit_message` starts with `chore(deps):` or `refactor(auto):`, return `GateResult(passed=True)`.
- Evaluation:
    1. If `total_additions > threshold`, return `GateResult(name="PR Size", passed=False, elapsed_seconds=elapsed, details=...)`.
    2. Otherwise, return `GateResult(passed=True)`.

```python
def check_pr_size(threshold: int = 400, commit_message: Optional[str] = None) -> GateResult:
    with tracer.start_as_current_span("gate.pr_size") as span:
        return _check_pr_size_impl(span, threshold, commit_message)


def _check_pr_size_impl(span: trace.Span, threshold: int, commit_message: Optional[str]) -> GateResult:
    start = time.time()
    # Bypass by prefix
    if commit_message and (commit_message.startswith("chore(deps):") or commit_message.startswith("refactor(auto):")):
        elapsed = time.time() - start
        span.set_attribute("gate.passed", True)
        span.set_attribute("gate.bypass", "prefix")
        return GateResult(name="PR Size", passed=True, elapsed_seconds=elapsed, details="Bypassed via commit prefix")

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--numstat"],
            capture_output=True, text=True, check=False, timeout=30,
        )
        if result.returncode != 0:
            elapsed = time.time() - start
            return GateResult(name="PR Size", passed=True, elapsed_seconds=elapsed, details="Skipped — git diff failed.")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        elapsed = time.time() - start
        return GateResult(name="PR Size", passed=True, elapsed_seconds=elapsed, details="Skipped — git not available.")

    total_additions = 0
    total_deletions = 0
    excluded_ext = {'.json', '.yaml', '.yml', '.png', '.jpg', '.jpeg', '.svg', '.lock', '.md', '.txt',
                    '.ttf', '.otf', '.mp4', '.mov', '.snap', '.csv', '.gif'}

    for line in result.stdout.strip().splitlines():
        parts = line.split('\t')
        if len(parts) < 3: continue
        adds, dels, path = parts[0], parts[1], parts[2]
        if adds == '-' or dels == '-': continue
        if any(path.endswith(ext) for ext in excluded_ext): continue
        total_additions += int(adds)
        total_deletions += int(dels)

    span.set_attribute("gate.total_additions", total_additions)
    span.set_attribute("gate.total_deletions", total_deletions)

    elapsed = time.time() - start
    logger.info("gate=pr_size total_additions=%d total_deletions=%d threshold=%d", total_additions, total_deletions, threshold)

    if total_deletions > total_additions:
        span.set_attribute("gate.passed", True)
        span.set_attribute("gate.bypass", "net_negative")
        return GateResult(name="PR Size", passed=True, elapsed_seconds=elapsed,
                          details=f"Net-negative change (+{total_additions}/-{total_deletions})")

    if total_additions > threshold:
        span.set_attribute("gate.passed", False)
        return GateResult(name="PR Size", passed=False, elapsed_seconds=elapsed,
                          details=f"PR size exceeds {threshold} lines (Found: {total_additions}). Split the PR or use 'refactor(auto):' prefix.")

    span.set_attribute("gate.passed", True)
    return GateResult(name="PR Size", passed=True, elapsed_seconds=elapsed,
                      details=f"PR size OK: {total_additions} additions (limit {threshold})")
```

#### MODIFY src/agent/commands/implement.py

- In the `apply_runbook` flow (or equivalent where gates are processed), call `gates.check_pr_size`.
- Retrieve the story title to use as the `commit_message` context for prefix bypass.

```python
# Inside the gate enforcement section of implement.py
story_title = story_data.get("title", "") # Ensure story_data is available
size_gate = gates.check_pr_size(commit_message=story_title)
if not size_gate.passed:
    console.print(f"[bold red]Gate Failed: PR Size[/bold red]\n{size_gate.details}")
    raise typer.Exit(code=1)
```

## Verification Plan

### Automated Tests
- [ ] `pytest .agent/tests/commands/test_gates_pr_size.py`:
  - `test_check_pr_size_under_limit`: 100 lines added → PASS.
  - `test_check_pr_size_over_limit`: 401 lines added → REJECT.
  - `test_check_pr_size_net_negative`: 500 deletions, 450 additions → PASS.
  - `test_check_pr_size_ignored_files`: 1000 lines in `package-lock.json` → PASS.
  - `test_check_pr_size_prefix_bypass`: `chore(deps): update` with 500 lines → PASS.

### Manual Verification
- [ ] Stage a change with >400 lines of code. Run `agent implement --story <ID>`. Verify the process exits with a clear error message.
- [ ] Rename the story to start with `refactor(auto):`, repeat the check, and verify it passes.
- [ ] Create a massive deletion (e.g., removing a large legacy file) and verify it passes despite being >400 lines.

## Definition of Done

### Documentation
- [ ] CHANGELOG.md updated with INFRA-092.
- [ ] API Documentation updated (Internal gate logic).

### Observability
- [ ] Logs are structured and free of PII (only LOC counts logged).
- [ ] OpenTelemetry spans added for `check_pr_size`.

### Testing
- [ ] Unit tests passed.
- [ ] Integration with `agent implement` verified.

## Copyright

Copyright 2026 Justin Cook
