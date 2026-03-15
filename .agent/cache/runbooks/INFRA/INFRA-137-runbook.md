# STORY-ID: INFRA-137: Preflight Rationalization

## State

ACCEPTED

## Goal Description

Rationalize the `agent preflight` pipeline by: (1) removing the `run_docs_check` gate now structurally enforced by `guards.enforce_docstrings()` (INFRA-136), (2) enhancing verdict caching to skip AI council roles that already passed on the same commit, and (3) adding `preflight_timing` structured log events. These changes reduce cycle time and improve observability without relaxing security or quality gates.

## Linked Journeys

- JRN-065

## Panel Review Findings

### @Architect
- **VERDICT**: APPROVE
- **SUMMARY**: Removing `run_docs_check` is safe — `guards.enforce_docstrings()` (INFRA-136) now catches missing docstrings at apply time.

### @Security
- **VERDICT**: APPROVE
- **SUMMARY**: `run_security_scan` is explicitly preserved. No security checks are weakened.

### @Qa
- **VERDICT**: APPROVE
- **SUMMARY**: Existing `run_docs_check` tests must be removed along with the function. Verdict caching is commit-aware so stale cache cannot cause false passes.

### @Observability
- **VERDICT**: APPROVE
- **SUMMARY**: `preflight_timing` adds structured timing. Uses `extra=` dict per repository standards.

## Codebase Introspection

### Targeted File Contents (from source)

#### .agent/src/agent/commands/gates.py (lines 226-280)
```python
def run_docs_check(filepaths: List[Path]) -> GateResult:
    """Verify that new/modified Python files have docstrings on public functions.

    Uses AST parsing — only checks top-level and class-level function definitions
    whose names do not start with ``_``.

    Args:
        filepaths: List of Python file paths to check.

    Returns:
        GateResult with pass/fail and list of undocumented functions.
    """
    start = time.time()
    missing: List[str] = []

    py_files = [f for f in filepaths if f.suffix == ".py" and f.exists()]
    if not py_files:
        elapsed = time.time() - start
        return GateResult(
            name="Documentation Check",
            passed=True,
            elapsed_seconds=elapsed,
            details="No Python files to check.",
        )

    for filepath in py_files:
        try:
            source = filepath.read_text(errors="ignore")
            tree = ast.parse(source, filename=str(filepath))
        except (SyntaxError, OSError) as exc:
            logger.warning("Could not parse %s: %s", filepath.name, exc)
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Only check public functions (not _private)
                if node.name.startswith("_"):
                    continue
                if ast.get_docstring(node) is None:
                    missing.append(f"{filepath.name}:{node.name}()")

    elapsed = time.time() - start
    if missing:
        return GateResult(
            name="Documentation Check",
            passed=False,
            elapsed_seconds=elapsed,
            details=f"Missing docstrings: {', '.join(missing[:10])}",
        )
    return GateResult(
        name="Documentation Check",
        passed=True,
        elapsed_seconds=elapsed,
        details=f"Checked {len(py_files)} file(s) — all documented.",
    )
```

#### .agent/src/agent/commands/implement.py (lines 862-864)
```python
        docs = gates.run_docs_check(modified_paths)
        gate_results.append(docs)
        _print_gate(docs)
```

#### .agent/src/agent/core/adk/orchestrator.py (lines 283-341)
```python
    async def _run_single_agent(agent):
        """Run a single agent and return parsed role_data dict."""
        role_name = agent.name
        if progress_callback:
            progress_callback(f"🤖 @{role_name} is reviewing (ADK)...")
        # ... (full function body)

    # Dispatch all agents concurrently
    if progress_callback:
        progress_callback(
            f"🚀 Dispatching {len(agents)} agents in parallel..."
        )
    agent_results = await asyncio.gather(
        *[_run_single_agent(agent) for agent in agents]
    )
```

#### .agent/src/agent/commands/check.py (lines 118-123)
```python
    # Apply panel engine override (INFRA-061)
    if panel_engine:
        config._panel_engine_override = panel_engine
        console.print(f"[dim]Panel engine override: {panel_engine}[/dim]")

    console.print("[bold blue]🚀 Initiating Preflight Sequence...[/bold blue]")
```

## Implementation Steps

### Step 1: Remove `run_docs_check` from gates.py

Enforced at source by `guards.enforce_docstrings()` (INFRA-136 AC-10). No longer needed as a post-apply gate.

#### [MODIFY] .agent/src/agent/commands/gates.py

```
<<<SEARCH
def run_docs_check(filepaths: List[Path]) -> GateResult:
    """Verify that new/modified Python files have docstrings on public functions.

    Uses AST parsing — only checks top-level and class-level function definitions
    whose names do not start with ``_``.

    Args:
        filepaths: List of Python file paths to check.

    Returns:
        GateResult with pass/fail and list of undocumented functions.
    """
    start = time.time()
    missing: List[str] = []

    py_files = [f for f in filepaths if f.suffix == ".py" and f.exists()]
    if not py_files:
        elapsed = time.time() - start
        return GateResult(
            name="Documentation Check",
            passed=True,
            elapsed_seconds=elapsed,
            details="No Python files to check.",
        )

    for filepath in py_files:
        try:
            source = filepath.read_text(errors="ignore")
            tree = ast.parse(source, filename=str(filepath))
        except (SyntaxError, OSError) as exc:
            logger.warning("Could not parse %s: %s", filepath.name, exc)
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Only check public functions (not _private)
                if node.name.startswith("_"):
                    continue
                if ast.get_docstring(node) is None:
                    missing.append(f"{filepath.name}:{node.name}()")

    elapsed = time.time() - start
    if missing:
        return GateResult(
            name="Documentation Check",
            passed=False,
            elapsed_seconds=elapsed,
            details=f"Missing docstrings: {', '.join(missing[:10])}",
        )
    return GateResult(
        name="Documentation Check",
        passed=True,
        elapsed_seconds=elapsed,
        details=f"Checked {len(py_files)} file(s) — all documented.",
    )
===
# INFRA-137: run_docs_check removed — now enforced at source by
# guards.enforce_docstrings() (INFRA-136 AC-10).
>>>
```

### Step 2: Remove `run_docs_check` call from implement.py

#### [MODIFY] .agent/src/agent/commands/implement.py

```
<<<SEARCH
        docs = gates.run_docs_check(modified_paths)
        gate_results.append(docs)
        _print_gate(docs)

        pr_size = gates.check_pr_size(commit_message=story_title)
===
        # INFRA-137: run_docs_check removed — enforced at source (INFRA-136).

        pr_size = gates.check_pr_size(commit_message=story_title)
>>>
```

### Step 3: Add commit-aware role skipping in orchestrator.py

Skip dispatching AI roles that already passed on the same commit SHA, using the existing `.preflight_result` cache.

#### [MODIFY] .agent/src/agent/core/adk/orchestrator.py

```
<<<SEARCH
    # Dispatch all agents concurrently
    if progress_callback:
        progress_callback(
            f"🚀 Dispatching {len(agents)} agents in parallel..."
        )
    agent_results = await asyncio.gather(
        *[_run_single_agent(agent) for agent in agents]
    )
===
    # ── INFRA-137: Skip roles that already PASS'd on this commit ──────────
    _head_sha = ""
    try:
        import subprocess as _sp
        _head_sha = _sp.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip()
    except Exception:
        pass

    _cached_commit = ""
    _cached_verdicts = previous_verdicts or {}
    if _cached_verdicts:
        try:
            import json as _cj
            _marker = config.cache_dir / ".preflight_result"
            if _marker.exists():
                _cached_commit = _cj.loads(_marker.read_text()).get("commit", "")
        except Exception:
            pass

    agents_to_run = []
    cached_results = []
    for agent in agents:
        role_name = agent.name
        cached_rv = _cached_verdicts.get(role_name, {})
        # Skip only if: same commit AND previous verdict was PASS
        if (
            _head_sha
            and _head_sha == _cached_commit
            and cached_rv.get("verdict") == "PASS"
        ):
            if progress_callback:
                progress_callback(
                    f"⏭️  @{role_name}: PASS (cached — same commit)"
                )
            cached_results.append({
                "name": role_name,
                "verdict": "PASS",
                "summary": cached_rv.get("summary", "Cached from previous run"),
                "findings": [],
                "required_changes": [],
                "references": {"cited": [], "valid": [], "invalid": []},
                "finding_validation": {"total": 0, "validated": 0, "filtered": 0},
                "_cached": True,
            })
        else:
            agents_to_run.append(agent)

    # Dispatch remaining agents concurrently
    if progress_callback:
        skipped = len(agents) - len(agents_to_run)
        progress_callback(
            f"🚀 Dispatching {len(agents_to_run)} agents in parallel"
            f" ({skipped} cached)..."
        )
    live_results = await asyncio.gather(
        *[_run_single_agent(agent) for agent in agents_to_run]
    )

    # Merge cached + live results in original agent order
    _live_iter = iter(live_results)
    _cached_iter = iter(cached_results)
    agent_results = []
    for agent in agents:
        role_name = agent.name
        cached_rv = _cached_verdicts.get(role_name, {})
        if (
            _head_sha
            and _head_sha == _cached_commit
            and cached_rv.get("verdict") == "PASS"
        ):
            agent_results.append(next(_cached_iter))
        else:
            agent_results.append(next(_live_iter))
>>>
```

### Step 4: Add `preflight_timing` structured log to check.py

#### [MODIFY] .agent/src/agent/commands/check.py

```
<<<SEARCH
    # Apply panel engine override (INFRA-061)
    if panel_engine:
        config._panel_engine_override = panel_engine
        console.print(f"[dim]Panel engine override: {panel_engine}[/dim]")

    console.print("[bold blue]🚀 Initiating Preflight Sequence...[/bold blue]")
===
    import time as _pf_time
    _preflight_start = _pf_time.time()

    # Apply panel engine override (INFRA-061)
    if panel_engine:
        config._panel_engine_override = panel_engine
        console.print(f"[dim]Panel engine override: {panel_engine}[/dim]")

    console.print("[bold blue]🚀 Initiating Preflight Sequence...[/bold blue]")
>>>
```

#### [MODIFY] .agent/src/agent/commands/check.py

```
<<<SEARCH
    console.print("[bold green]✅ Preflight checks passed![/bold green]")

    # INFRA-138: Always write cache on successful completion so `agent pr`
    # can detect the pass without re-running preflight.
    _write_preflight_cache(story_id, "PASS")
===
    _preflight_duration_ms = int((_pf_time.time() - _preflight_start) * 1000)
    logger.info(
        "preflight_timing",
        extra={
            "story_id": story_id,
            "duration_ms": _preflight_duration_ms,
            "verdict": "PASS",
        },
    )

    console.print(
        f"[bold green]✅ Preflight checks passed![/bold green] "
        f"[dim]({_preflight_duration_ms}ms)[/dim]"
    )

    # INFRA-138: Always write cache on successful completion so `agent pr`
    # can detect the pass without re-running preflight.
    _write_preflight_cache(story_id, "PASS")
>>>
```

### Step 5: Update tests

#### [MODIFY] .agent/tests/commands/test_gates.py

Remove `TestRunDocsCheck` class and `run_docs_check` from imports/composability tests.

```
<<<SEARCH
from agent.commands.gates import (
    GateResult,
    check_commit_message,
    check_commit_size,
    check_domain_isolation,
    log_skip_audit,
    run_docs_check,
    run_qa_gate,
    run_security_scan,
)
===
from agent.commands.gates import (
    GateResult,
    check_commit_message,
    check_commit_size,
    check_domain_isolation,
    log_skip_audit,
    run_qa_gate,
    run_security_scan,
)
>>>
```

```
<<<SEARCH
# ── Docs Check ────────────────────────────────────────────────


class TestRunDocsCheck:
    def test_documented_functions_pass(self, clean_py_file: Path):
        result = run_docs_check([clean_py_file])
        assert result.passed is True
        assert result.name == "Documentation Check"

    def test_undocumented_functions_blocked(self, bad_py_file: Path):
        result = run_docs_check([bad_py_file])
        assert result.passed is False
        assert "undocumented" in result.details

    def test_private_functions_ignored(self, tmp_path: Path):
        """Private functions (starting with _) should not be checked."""
        f = tmp_path / "private.py"
        f.write_text(
            "def _helper():\n"
            "    return 42\n"
        )
        result = run_docs_check([f])
        assert result.passed is True

    def test_no_python_files(self, tmp_path: Path):
        txt = tmp_path / "readme.txt"
        txt.write_text("hello")
        result = run_docs_check([txt])
        assert result.passed is True
        assert "No Python files" in result.details

    def test_empty_file_list(self):
        result = run_docs_check([])
        assert result.passed is True


# ── Composability ─────────────────────────────────────────────


class TestGatesComposable:
    def test_all_gates_independent(
        self,
        clean_py_file: Path,
        security_patterns_file: Path,
    ):
        """Each gate can run independently and results are composable."""
        sec = run_security_scan([clean_py_file], security_patterns_file)
        qa = run_qa_gate("true")
        docs = run_docs_check([clean_py_file])

        results = [sec, qa, docs]
        assert all(isinstance(r, GateResult) for r in results)
        assert all(r.passed for r in results)
        assert all(r.elapsed_seconds >= 0 for r in results)
===
# ── INFRA-137: TestRunDocsCheck removed — enforced at source (INFRA-136). ──


# ── Composability ─────────────────────────────────────────────


class TestGatesComposable:
    def test_all_gates_independent(
        self,
        clean_py_file: Path,
        security_patterns_file: Path,
    ):
        """Each gate can run independently and results are composable."""
        sec = run_security_scan([clean_py_file], security_patterns_file)
        qa = run_qa_gate("true")

        results = [sec, qa]
        assert all(isinstance(r, GateResult) for r in results)
        assert all(r.passed for r in results)
        assert all(r.elapsed_seconds >= 0 for r in results)
>>>
```

#### [MODIFY] .agent/tests/commands/test_implement_updates_journey.py

```
<<<SEARCH
         patch("agent.commands.implement.gates.run_docs_check") as mock_docs:
         
        # Mock gates to pass
        from agent.commands.gates import GateResult
        mock_sec.return_value = GateResult("Security", True, 0.1, "")
        mock_qa.return_value = GateResult("QA", True, 0.1, "")
        mock_docs.return_value = GateResult("Docs", True, 0.1, "")
===
        # Mock gates to pass
        from agent.commands.gates import GateResult
        mock_sec.return_value = GateResult("Security", True, 0.1, "")
        mock_qa.return_value = GateResult("QA", True, 0.1, "")
>>>
```

#### [MODIFY] .agent/tests/core/check/test_implement_gate.py

```
<<<SEARCH
            mock_gates.run_docs_check.return_value = _make_gate_result(True)
            mock_gates.check_pr_size.return_value = _make_gate_result(True)
===
            mock_gates.check_pr_size.return_value = _make_gate_result(True)
>>>
```

## Verification Plan

### Automated Tests

```bash
cd .agent && uv run pytest tests/ -v --tb=short
```

### Manual Verification

- Run `agent preflight --story INFRA-137 --base main` and confirm `preflight_timing` log is emitted with `duration_ms`
- Run preflight twice on same commit — second run should show `⏭️ @role: PASS (cached)` for already-passed roles

## Definition of Done

- [ ] All existing tests pass (minus removed `TestRunDocsCheck`)
- [ ] `preflight_timing` structured log emitted on every preflight completion
- [ ] Roles cached on same commit are skipped on re-run

## Copyright

Copyright 2026 Justin Cook