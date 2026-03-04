# INFRA-091: Static Commit Atomicity Checks

## State

ACCEPTED

## Goal Description

Add three static gate functions to `gates.py` that enforce commit-level atomicity: a commit size check (20/100 rule), a commit message lint (compound "and" detection + conventional commit validation), and a domain isolation check (core/ vs addons/ mixing). All functions are pure, fast (<1s), and follow the existing `GateResult` pattern.

## Linked Journeys

- JRN-065: Circuit Breaker During Implementation

## Panel Review Findings

**@Architect**: Clean scope — three pure functions added to an existing module with an established pattern (`GateResult`). No new dependencies. No cross-cutting concerns. The `check_commit_size` function should use `git diff --cached --numstat` for accurate line counts rather than re-reading file contents, keeping it consistent with how the rest of the pipeline measures changes.

**@QA**: Each function is independently testable with `tmp_path` fixtures following the existing test structure in `test_gates.py`. The "And" test needs careful edge case handling — words like "command", "standard", "bandwidth" contain "and" but are not compound actions. Recommend matching `" and "` (with spaces) in the message body only, not the prefix.

**@Security**: No secrets, no PII, no external calls. Pure string/path analysis. No concerns.

**@Product**: These are warning-level gates (not blocking) for commit size and message checks, but `check_domain_isolation` is a hard FAIL. This matches the story's intent — developers get feedback without being blocked on minor issues.

**@Observability**: Each function already returns structured `GateResult` with timing. Recommend adding `logger.info` with JSON-style fields for threshold decisions to support audit queries.

**@Docs**: No user-facing docs needed — these are internal governance functions. CHANGELOG entry per convention.

**@Compliance**: Follows existing `GateResult` + `log_skip_audit` patterns. SOC2 audit trail maintained.

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Add type hint `-> GateResult` to all existing gate functions for consistency (currently missing on some)
- [ ] Future: Surface gate names in `/preflight` summary report (per @Product advisory — track as separate story)

## Implementation Steps

### Commit Size Gate

#### [MODIFY] [gates.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/commands/gates.py)

Add `check_commit_size` function after the existing `run_docs_check` function (after line 228):

- **Signature**: `check_commit_size(max_per_file: int = 20, max_total: int = 100) -> GateResult`
- **Logic**:
  1. Run `git diff --cached --numstat` via `subprocess.run` to get per-file addition/deletion counts.
  2. Parse output: each line is `additions\tdeletions\tfilename`.
  3. Sum `additions + deletions` per file and total.
  4. If any single file exceeds `max_per_file` → `passed=False`, detail which file(s).
  5. If total exceeds `max_total` → `passed=False`, detail total count.
  6. Both thresholds can trigger independently — report all violations.
  7. Handle `subprocess` errors gracefully (e.g., not in a git repo → pass with "Skipped" detail).
- **Logging**: `logger.info("commit_size_check", extra={"max_file": max_file_count, "max_total": total_count, "passed": bool})`.
- **Performance**: Single subprocess call, string parsing only — well under 1s.

```python
def check_commit_size(max_per_file: int = 20, max_total: int = 100) -> GateResult:
    """Check staged changes against per-file and total line count thresholds.

    Warns if any single file has more than max_per_file lines changed,
    or if the total across all files exceeds max_total.

    Args:
        max_per_file: Maximum lines changed per file before warning.
        max_total: Maximum total lines changed before warning.

    Returns:
        GateResult with pass/fail and details of any threshold violations.
    """
    start = time.time()
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--numstat"],
            capture_output=True, text=True, check=False, timeout=30,
        )
        if result.returncode != 0:
            elapsed = time.time() - start
            return GateResult(
                name="Commit Size",
                passed=True,
                elapsed_seconds=elapsed,
                details="Skipped — git diff failed.",
            )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        elapsed = time.time() - start
        return GateResult(
            name="Commit Size", passed=True,
            elapsed_seconds=elapsed, details="Skipped — git not available.",
        )

    violations: List[str] = []
    total_changed = 0
    max_file_changed = 0

    for line in result.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        # Binary files show '-' for additions/deletions
        try:
            additions = int(parts[0])
            deletions = int(parts[1])
        except ValueError:
            continue
        filename = parts[2]
        file_changed = additions + deletions
        total_changed += file_changed
        max_file_changed = max(max_file_changed, file_changed)

        if file_changed > max_per_file:
            violations.append(f"{filename}: {file_changed} lines (limit {max_per_file})")

    if total_changed > max_total:
        violations.append(f"Total: {total_changed} lines (limit {max_total})")

    elapsed = time.time() - start
    logger.info(
        "gate=commit_size max_file_count=%d total=%d passed=%s",
        max_file_changed, total_changed, not bool(violations),
    )
    if violations:
        return GateResult(
            name="Commit Size", passed=False,
            elapsed_seconds=elapsed, details="; ".join(violations),
        )
    return GateResult(
        name="Commit Size", passed=True,
        elapsed_seconds=elapsed,
        details=f"Total: {total_changed} lines — within limits.",
    )
```

### Commit Message Lint

#### [MODIFY] [gates.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/commands/gates.py)

Add `check_commit_message` function after `check_commit_size`:

- **Signature**: `check_commit_message(message: str) -> GateResult`
- **Logic**:
  1. **Conventional Commit Validation**: Parse the message for a valid prefix (`feat:`, `fix:`, `refactor:`, `chore:`, `docs:`, `test:`, `ci:`, `style:`, `perf:`, `build:`). Prefix may include a scope, e.g. `feat(cli):`. If no valid prefix → `passed=False`.
  2. **"And" Test**: After the prefix, check if the message body contains `" and "` (space-delimited to avoid false positives on words like "command"). If found → `passed=False`.
  3. Both checks run independently; report all violations.
- **Edge cases**: Empty message → fail. Message with only a prefix and no description → pass (prefix is valid). Multi-line messages: only the subject line (first line) is checked for `" and "` — body text is descriptive and intentionally exempt.

```python
CONVENTIONAL_PREFIXES = {
    "feat", "fix", "refactor", "chore", "docs",
    "test", "ci", "style", "perf", "build",
}

def check_commit_message(message: str) -> GateResult:
    """Validate commit message for conventional format and single-purpose.

    Checks:
    1. Message starts with a valid conventional commit prefix.
    2. Message body does not contain ' and ' joining distinct actions.

    Args:
        message: The full commit message string.

    Returns:
        GateResult with pass/fail and details.
    """
    start = time.time()
    if not message.strip():
        elapsed = time.time() - start
        return GateResult(
            name="Commit Message", passed=False,
            elapsed_seconds=elapsed, details="Empty commit message.",
        )

    violations: List[str] = []
    first_line = message.strip().splitlines()[0]

    # 1. Conventional commit prefix
    prefix_match = re.match(r"^(\w+)(?:\([^)]*\))?:", first_line)
    if not prefix_match or prefix_match.group(1) not in CONVENTIONAL_PREFIXES:
        violations.append(
            f"Missing conventional prefix. Expected one of: "
            f"{', '.join(sorted(CONVENTIONAL_PREFIXES))}"
        )

    # 2. "And" test — check body after prefix
    colon_idx = first_line.find(":")
    body = first_line[colon_idx + 1:] if colon_idx != -1 else first_line
    if " and " in body.lower():
        violations.append('Compound message — contains " and " (split into separate commits)')

    elapsed = time.time() - start
    if violations:
        return GateResult(
            name="Commit Message", passed=False,
            elapsed_seconds=elapsed, details="; ".join(violations),
        )
    return GateResult(
        name="Commit Message", passed=True,
        elapsed_seconds=elapsed, details="Valid conventional commit.",
    )
```

### Domain Isolation Gate

#### [MODIFY] [gates.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/commands/gates.py)

Add `check_domain_isolation` function after `check_commit_message`:

- **Signature**: `check_domain_isolation(filepaths: List[Path]) -> GateResult`
- **Logic**:
  1. Classify each file path: does it contain a `core/` component? An `addons/` component?
  2. Use `Path.parts` for reliable component matching (not string prefix).
  3. If both `core/` and `addons/` files are present → `passed=False`.
  4. If only one domain or neither → `passed=True`.

```python
def check_domain_isolation(filepaths: List[Path]) -> GateResult:
    """Verify that a changeset does not mix core/ and addons/ domains.

    Args:
        filepaths: List of file paths in the changeset.

    Returns:
        GateResult — FAIL if both core/ and addons/ are touched.
    """
    start = time.time()
    has_core = any("core" in p.parts for p in filepaths)
    has_addons = any("addons" in p.parts for p in filepaths)

    elapsed = time.time() - start
    if has_core and has_addons:
        return GateResult(
            name="Domain Isolation", passed=False,
            elapsed_seconds=elapsed,
            details="Changeset touches both core/ and addons/ — split into separate commits.",
        )
    return GateResult(
        name="Domain Isolation", passed=True,
        elapsed_seconds=elapsed,
        details="Single domain.",
    )
```

### Tests

#### [MODIFY] [test_gates.py](file:///Users/jcook/repo/agentic-dev/.agent/tests/commands/test_gates.py)

Add three test classes after the existing `TestLogSkipAudit` class (after line 230):

**`TestCheckCommitSize`** (~40 lines):
- `test_under_limit`: Mock `git diff --cached --numstat` returning 5 lines in one file → `passed=True`.
- `test_over_per_file_limit`: Mock returning 25 lines in one file → `passed=False`, file named in details.
- `test_over_total_limit`: Mock returning 10 files × 15 lines each (150 total) → `passed=False`, "Total" in details.
- `test_empty_changeset`: Mock returning empty output → `passed=True`.
- `test_binary_file_skipped`: Mock returning `- - binary.png` → skipped gracefully via `ValueError` catch, `passed=True`.
- `test_git_not_available`: Mock `FileNotFoundError` → `passed=True`, "Skipped" in details.

**`TestCheckCommitMessage`** (~45 lines):
- `test_valid_single_type`: `"feat(cli): add new flag"` → `passed=True`.
- `test_compound_and_message`: `"feat: add logging and update tests"` → `passed=False`, `" and "` in details.
- `test_missing_prefix`: `"did some stuff"` → `passed=False`, "conventional prefix" in details.
- `test_empty_message`: `""` → `passed=False`, "Empty" in details.
- `test_word_containing_and`: `"fix: handle command error"` → `passed=True` (no false positive on "command").
- `test_scoped_prefix`: `"refactor(core): extract helper"` → `passed=True`.
- `test_and_in_body_line_ignored`: `"feat: add logging\n\nThis updates and improves tracing"` → `passed=True` (body-line `" and "` is intentionally exempt).

**`TestCheckDomainIsolation`** (~25 lines):
- `test_core_only`: paths with `core/` component → `passed=True`.
- `test_addons_only`: paths with `addons/` component → `passed=True`.
- `test_mixed_domains`: paths with both → `passed=False`, "core/ and addons/" in details.
- `test_no_domain_paths`: paths without either → `passed=True`.
- `test_empty_paths`: empty list → `passed=True`.

All tests use `unittest.mock.patch("subprocess.run")` for `check_commit_size` and `Path` objects for the others — matching existing test patterns in the file.

## Verification Plan

### Automated Tests

- [ ] `pytest .agent/tests/commands/test_gates.py -k "CheckCommitSize" -v`
- [ ] `pytest .agent/tests/commands/test_gates.py -k "CheckCommitMessage" -v`
- [ ] `pytest .agent/tests/commands/test_gates.py -k "CheckDomainIsolation" -v`
- [ ] `pytest .agent/tests/commands/test_gates.py -v` (full regression — all existing tests still pass)

### Manual Verification

- [ ] Stage a >20 line single-file change and run `check_commit_size()` in a Python REPL — verify warning details
- [ ] Test `check_commit_message("feat: add logging and update tests")` — verify "and" detection

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated with INFRA-091 entry
- [ ] README.md updated (if applicable — likely N/A, internal functions)

### Observability

- [ ] Logs are structured and free of PII
- [ ] Metrics added for threshold violations

### Testing

- [ ] Unit tests passed
- [ ] Integration tests passed

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0
