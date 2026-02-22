# INFRA-058: Journey-Linked Regression Tests

## State

ACCEPTED

## Goal Description

Enforce a link between user journeys and their corresponding regression tests. Extend `validate_journey` with state-aware test enforcement, add `env -u VIRTUAL_ENV uv run agent journey coverage` and `env -u VIRTUAL_ENV uv run agent journey backfill-tests` commands, and integrate a journey coverage gate into `env -u VIRTUAL_ENV uv run agent preflight`.

## Linked Journeys

- JRN-044: Introduce User Journeys as First-Class Artifacts
- JRN-053: Journey Test Coverage

## Panel Review Findings

**@Architect**:

- Phased rollout (warning→blocking) is correct given 50+ existing journeys with `tests: []`.
- `backfill-tests` command with auto-generated stubs is the migration path.
- Coverage levels: linked / missing / unlinked / stale.
- ADR-005 (AI-Driven Governance Preflight) correctly linked.

**@QA**:

- Negative tests well-defined (DRAFT exempt, COMMITTED+empty→fail, nonexistent file→distinct error).
- Per-file status (AC-7) critical for incremental adoption.
- Path resolution relative to `config.project_root` is correct.

**@Security**:

- Validate against path traversal (`../../` and absolute paths outside project root).
- Stubs never overwrite existing files.
- Generated logs must not contain PII (per ADR-027).

**@Product**:

- Rich table output for coverage command (`--json` for CI).
- Convention-based path suggestions (`tests/journeys/test_jrn_XXX.py`).
- Default action = generate stubs, not skip.

**@Backend**:

- `@pytest.mark.journey("JRN-XXX")` marker for targeted execution.
- `check_journey_coverage()` as standalone function returning structured results.
- Type hints enforced throughout. Typer CLI commands are sync (ADR-028).

**@Observability**:

- OpenTelemetry span for journey coverage check in preflight.
- Structured logging for coverage metrics.

**@Compliance**:

- Persistable coverage report for SOC 2 CC7.1 evidence.
- Coverage metric tracked over time for `env -u VIRTUAL_ENV uv run agent audit`.

**@Docs**:

- Journey template comment for `tests` field.
- README updated with `env -u VIRTUAL_ENV uv run agent journey coverage` and `env -u VIRTUAL_ENV uv run agent journey backfill-tests`.

## Implementation Steps

### Step 1 — Enhance `validate_journey` (AC-1, AC-2, AC-7)

#### MODIFY `journey.py` — `validate_journey()` (L228-295)

Insert state-aware test enforcement AFTER the existing `recommended` checks (L280) and BEFORE the report section (L283):

```python
# --- State-aware test enforcement (INFRA-058) ---
state = data.get("state", "DRAFT").upper()
impl_tests = data.get("implementation", {}).get("tests", [])

if state in ("COMMITTED", "ACCEPTED"):
    if not impl_tests:
        errors.append(
            "COMMITTED/ACCEPTED journey requires non-empty 'implementation.tests'"
        )
    else:
        from agent.core.config import config
        for test_path_str in impl_tests:
            test_path = Path(test_path_str)
            # Reject absolute paths and traversal
            if test_path.is_absolute():
                errors.append(f"Test path must be relative: '{test_path_str}'")
                continue
            try:
                resolved = (config.project_root / test_path).resolve()
                resolved.relative_to(config.project_root.resolve())
            except ValueError:
                errors.append(f"Test path escapes project root: '{test_path_str}'")
                continue
            if not resolved.exists():
                errors.append(f"Test file not found: '{test_path_str}'")
            # Extension-agnostic: .py, .yaml, .spec.ts all valid
```

**Key points**:

- Uses existing `errors`/`warnings` lists (L253-254)
- DRAFT journeys skip this block entirely
- Per-file status: each test path validated individually (AC-7)
- Path traversal rejection uses `resolve().relative_to()` pattern

---

### Step 2 — Add `coverage` subcommand (AC-4)

#### MODIFY `journey.py` — new `coverage()` command

Register on existing `app = typer.Typer()` (L31). Add after `validate_journey` (after L295):

```python
@app.command()
def coverage(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON for CI"),
    scope: Optional[str] = typer.Option(None, "--scope", help="Filter by scope (INFRA, MOBILE, WEB)"),
) -> None:
    """Report journey → test mapping with coverage status."""
    from agent.core.config import config

    journeys_dir = config.project_root / ".agent" / "cache" / "journeys"
    if not journeys_dir.exists():
        console.print("[yellow]No journeys directory found.[/yellow]")
        raise typer.Exit(0)

    results = []
    for scope_dir in sorted(journeys_dir.iterdir()):
        if not scope_dir.is_dir():
            continue
        if scope and scope_dir.name.upper() != scope.upper():
            continue
        for jfile in sorted(scope_dir.glob("JRN-*.yaml")):
            data = yaml.safe_load(jfile.read_text())
            state = data.get("state", "DRAFT").upper()
            tests = data.get("implementation", {}).get("tests", [])
            jid = data.get("id", jfile.stem)
            title = data.get("title", "")

            statuses = []
            for t in tests:
                resolved = (config.project_root / t).resolve()
                exists = resolved.exists()
                statuses.append({"path": t, "exists": exists})

            if not tests:
                overall = "❌ No tests"
            elif all(s["exists"] for s in statuses):
                overall = "✅ Linked"
            else:
                overall = "⚠️ Missing"

            results.append({
                "id": jid, "title": title, "state": state,
                "tests": len(tests), "status": overall, "details": statuses,
            })

    if json_output:
        import json
        console.print_json(json.dumps(results))
        return

    # Rich table
    from rich.table import Table
    table = Table(title="Journey Test Coverage")
    table.add_column("Journey ID", style="cyan")
    table.add_column("Title")
    table.add_column("State")
    table.add_column("Tests", justify="right")
    table.add_column("Status")
    for r in results:
        table.add_row(r["id"], r["title"][:40], r["state"], str(r["tests"]), r["status"])
    console.print(table)

    linked = sum(1 for r in results if "✅" in r["status"])
    total = sum(1 for r in results if r["state"] in ("COMMITTED", "ACCEPTED"))
    pct = (linked / total * 100) if total else 0
    console.print(f"\nCoverage: {linked}/{total} COMMITTED+ journeys linked ({pct:.0f}%)")
```

---

### Step 3 — Add `backfill-tests` subcommand (AC-6)

#### MODIFY `journey.py` — new `backfill_tests()` command

Register on existing `app`. Add after `coverage`:

```python
@app.command("backfill-tests")
def backfill_tests(
    scope: Optional[str] = typer.Option(None, "--scope", help="Filter by scope"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
) -> None:
    """Generate pytest test stubs for COMMITTED journeys with empty tests."""
    from agent.core.config import config

    journeys_dir = config.project_root / ".agent" / "cache" / "journeys"
    tests_dir = config.project_root / "tests" / "journeys"
    tests_dir.mkdir(parents=True, exist_ok=True)

    generated = 0
    for scope_dir in sorted(journeys_dir.iterdir()):
        if not scope_dir.is_dir():
            continue
        if scope and scope_dir.name.upper() != scope.upper():
            continue
        for jfile in sorted(scope_dir.glob("JRN-*.yaml")):
            data = yaml.safe_load(jfile.read_text())
            state = data.get("state", "DRAFT").upper()
            tests = data.get("implementation", {}).get("tests", [])
            jid = data.get("id", jfile.stem)

            if state != "COMMITTED" or tests:
                continue

            slug = jid.lower().replace("-", "_")
            stub_path = tests_dir / f"test_{slug}.py"

            if stub_path.exists():
                console.print(f"[yellow]⚠️  Skipping {jid}: {stub_path} already exists[/yellow]")
                continue

            if dry_run:
                console.print(f"[dim]Would create: {stub_path}[/dim]")
                generated += 1
                continue

            # Generate stub from journey assertions
            steps = data.get("steps", [])
            test_funcs = []
            for i, step in enumerate(steps, 1):
                assertions = step.get("assertions", [])
                assertion_comments = "\n".join(f"    # {a}" for a in assertions) if assertions else "    # No assertions defined"
                test_funcs.append(f'''
@pytest.mark.journey("{jid}")
def test_{slug}_step_{i}():
    """Step {i}: {step.get('action', 'unnamed')[:60]}"""
{assertion_comments}
    pytest.skip("Not yet implemented")
''')

            content = f'''"""Auto-generated test stubs for {jid}."""
import pytest

{"".join(test_funcs)}'''

            stub_path.write_text(content)

            # Update journey YAML
            if "implementation" not in data:
                data["implementation"] = {}
            data["implementation"]["tests"] = [str(stub_path.relative_to(config.project_root))]
            jfile.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

            console.print(f"[green]✅ Generated: {stub_path}[/green]")
            generated += 1

    console.print(f"\n{'Would generate' if dry_run else 'Generated'} {generated} test stub(s)")
```

**Key points**:

- Stubs use `@pytest.mark.journey("JRN-XXX")` marker
- Stubs contain `pytest.skip("Not yet implemented")` — pass CI but are clearly incomplete
- Never overwrites existing files
- Updates journey YAML `implementation.tests` field

---

### Step 4 — Enhance journey creation workflow (AC-5)

#### MODIFY `journey.py` — `new_journey()` (after file write at L211)

Insert test linking prompt AFTER `file_path.write_text(content)` (L211) and BEFORE the auto-sync block (L215):

```python
    # Prompt to link test files (INFRA-058)
    test_paths = Prompt.ask(
        "[bold]Link test files? [paths or Enter to generate stub][/bold]",
        default=""
    )
    if test_paths.strip():
        # User provided paths
        paths = [p.strip() for p in test_paths.split(",")]
    else:
        # Generate stub (default action)
        slug = journey_id.lower().replace("-", "_")
        stub_dir = Path(config.project_root) / "tests" / "journeys"
        stub_dir.mkdir(parents=True, exist_ok=True)
        stub_path = stub_dir / f"test_{slug}.py"
        if not stub_path.exists():
            stub_path.write_text(f'"""Auto-generated stub for {journey_id}."""\nimport pytest\n\n@pytest.mark.journey("{journey_id}")\ndef test_{slug}():\n    pytest.skip("Not yet implemented")\n')
            console.print(f"[green]📝 Generated test stub: {stub_path}[/green]")
        paths = [str(stub_path.relative_to(config.project_root))]

    # Update the journey YAML with test paths
    data = yaml.safe_load(file_path.read_text())
    if "implementation" not in data:
        data["implementation"] = {}
    data["implementation"]["tests"] = paths
    file_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
```

---

### Step 5 — Preflight journey coverage gate (AC-3)

#### MODIFY `check.py` — add `check_journey_coverage()` and preflight integration

Add standalone function BEFORE `preflight()` (before L173):

```python
def check_journey_coverage(
    repo_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Check journey → test coverage. Returns structured results.

    Returns:
        Dict with keys: passed (bool), total, linked, missing, warnings (list[str])
    """
    from agent.core.config import config

    root = repo_root or config.project_root
    journeys_dir = root / ".agent" / "cache" / "journeys"
    result = {"passed": True, "total": 0, "linked": 0, "missing": 0, "warnings": []}

    if not journeys_dir.exists():
        return result

    for scope_dir in sorted(journeys_dir.iterdir()):
        if not scope_dir.is_dir():
            continue
        for jfile in sorted(scope_dir.glob("JRN-*.yaml")):
            try:
                data = yaml.safe_load(jfile.read_text())
            except Exception:
                continue
            state = (data.get("state") or "DRAFT").upper()
            if state not in ("COMMITTED", "ACCEPTED"):
                continue

            result["total"] += 1
            tests = data.get("implementation", {}).get("tests", [])
            jid = data.get("id", jfile.stem)

            if not tests:
                result["missing"] += 1
                result["warnings"].append(f"{jid}: No tests linked")
                continue

            all_exist = True
            for t in tests:
                tp = Path(t)
                if tp.is_absolute():
                    result["warnings"].append(f"{jid}: Absolute test path '{t}'")
                    all_exist = False
                    continue
                if not (root / tp).exists():
                    result["warnings"].append(f"{jid}: Test file not found: '{t}'")
                    all_exist = False

            if all_exist:
                result["linked"] += 1
            else:
                result["missing"] += 1

    return result
```

Insert journey coverage gate in `preflight()` AFTER the ADR enforcement gate (after L657) and BEFORE the "Get Changed Files" section (L659):

```python
    # 1.8 Journey Coverage Check (Phase 1: Warning — INFRA-058)
    console.print("\n[bold blue]📋 Checking Journey Test Coverage...[/bold blue]")
    coverage_result = check_journey_coverage()
    json_report["journey_coverage"] = coverage_result

    if coverage_result["warnings"]:
        console.print(
            f"[yellow]⚠️  Journey Coverage: {coverage_result['linked']}/{coverage_result['total']}"
            f" COMMITTED journeys linked[/yellow]"
        )
        for w in coverage_result["warnings"][:10]:  # Cap output
            console.print(f"  [yellow]• {w}[/yellow]")
    else:
        console.print("[green]✅ Journey Coverage: All linked.[/green]")
```

**Phase 1**: Warnings only. Phase 2 (future): add `if not coverage_result["passed"]: raise typer.Exit(1)` when ≥80% coverage reached.

---

### Step 6 — Update journey template (AC-8)

#### MODIFY `templates/journey-template.yaml` (L40-43)

```yaml
implementation:
  routes: []
  files: []
  tests: [] # Required for COMMITTED journeys. List paths to test files relative to project root.
```

---

## Verification Plan

### Automated Tests

- [ ] **Unit — validate_journey**: Rejects COMMITTED journey with empty `implementation.tests`. Accepts DRAFT journey with empty tests. Rejects COMMITTED journey with nonexistent test file (distinct error). Reports per-file status for mixed existing/missing files.
- [ ] **Unit — path validation**: Path traversal (`../../etc/passwd`) rejected. Absolute paths rejected. Extension-agnostic (`.py`, `.yaml`, `.spec.ts` all valid).
- [ ] **Unit — stub generation**: `backfill-tests` generates valid pytest file with `@pytest.mark.journey` marker. No overwrite of existing files.
- [ ] **Unit — check_journey_coverage**: Returns correct counts for fixture journeys with mixed states.
- [ ] **Integration — coverage command**: `env -u VIRTUAL_ENV uv run agent journey coverage` produces expected table output.
- [ ] **Integration — preflight**: Preflight warns (Phase 1) on COMMITTED journey with missing tests.

### Manual Verification

- [ ] `env -u VIRTUAL_ENV uv run agent journey coverage` displays rich table with correct status icons
- [ ] `env -u VIRTUAL_ENV uv run agent journey backfill-tests --dry-run` previews without writing
- [ ] `env -u VIRTUAL_ENV uv run agent preflight --ai` shows journey coverage warning section
- [ ] New journey creation prompts for test file linking

## Definition of Done

- [ ] CHANGELOG.md updated
- [ ] README.md updated with new commands
- [ ] OpenTelemetry span for coverage check in preflight
- [ ] Structured logging, no PII
- [ ] Unit + integration tests passing
