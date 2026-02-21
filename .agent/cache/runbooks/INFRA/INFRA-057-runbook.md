# INFRA-057: ADR-Driven Deterministic Lint Rules

## State

COMMITTED

## Goal Description

Automate enforcement of Architectural Decision Records (ADRs) by parsing `enforcement` fenced blocks from ACCEPTED ADRs and running them as deterministic regex-based lint rules. This eliminates reliance on AI interpretation for known constraints, reduces preflight latency for deterministic checks, and produces structured, auditable output.

## Linked Journeys

- JRN-036 (Interactive Preflight Repair)
- JRN-052 (ADR Lint Enforcement)

## Panel Review Findings

**@Architect**: ADR-025 already contains a canonical `enforcement` block (lines 41–51). The parser must handle the existing format: ` ```enforcement` fenced blocks containing YAML lists with `type`, `pattern`, `scope`, `violation_message` keys. New rules follow the `run_linter` dispatcher pattern in `lint.py` (line 135–203). The `run_adr_enforcement()` function should integrate alongside `run_ruff`, `run_shellcheck`, `run_eslint`, `run_markdownlint` in the `lint()` command (line 322–380).

**@QA**: Tests must cover: YAML parsing (valid/malformed/multi-block), regex matching per line, 5s timeout via `signal.SIGALRM`, scope glob validation (reject absolute paths), EXC-* exception suppression (EXC-001/EXC-002 exist in `.agent/adrs/`), ADR status filtering (only ACCEPTED), and preflight integration. Negative tests for DRAFT/SUPERSEDED ADRs and invalid regex are critical.

**@Security**: The 5-second `signal.SIGALRM` timeout mitigates ReDoS. Scope globs must be validated as relative paths resolved against `config.repo_root` to prevent directory traversal. Exception records (EXC-*) must only suppress matching violations, never bypass the entire linter. All regex patterns are applied per-line (no multi-line `re.DOTALL`) to limit blast radius.

**@Product**: Structured output follows `file:line:col: ADR-NNN message` convention (matching ruff). The `--adr-only` flag allows targeted execution. Preflight shows a separate "ADR Enforcement" section before the AI panel.

**@Observability**: Add `tracer.start_as_current_span("lint.adr_enforcement")` wrapping the function, with attributes for `adr_count`, `rule_count`, `violation_count`, `exception_count`, matching the existing `lint.{name}` span pattern.

**@Compliance**: Deterministic enforcement provides SOC 2 CC7.1 audit evidence independent of AI availability. EXC-* integration (ADR-021) ensures exceptions are documented. Apache 2.0 headers required on new files.

**@Backend**: Use existing `config` singleton from `agent.core.config` — do NOT create a `Configuration` class. Parse ADR state from the `## State` section header. Use `pathlib.Path` and `fnmatch` for scope globbing. `yaml.safe_load()` for enforcement block parsing.

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Convert `print()` calls to `console.print()` with Rich markup in new ADR lint functions
- [ ] Ensure consistent error handling in `run_adr_enforcement()` matching `run_linter` pattern

## Implementation Steps

### Phase 1: ADR Parsing & Enforcement Engine

#### [MODIFY] [lint.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/commands/lint.py)

**Step 1.1 — Add `parse_adr_enforcement_blocks()` function**

Parse ` ```enforcement` fenced blocks (NOT ` ```yaml enforcement`) from ADR markdown content. ADR-025 (line 41) uses this format:

```python
import re
import yaml
import signal
import fnmatch
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

def parse_adr_enforcement_blocks(content: str) -> List[Dict[str, str]]:
    """Extract enforcement rules from ```enforcement fenced blocks in ADR content.
    
    Returns list of dicts with keys: type, pattern, scope, violation_message
    """
    blocks = []
    # Match ```enforcement ... ``` blocks (ADR-025 canonical format)
    matches = re.findall(r"```enforcement\s*\n(.*?)\n```", content, re.DOTALL)
    for match in matches:
        try:
            parsed = yaml.safe_load(match)
            if isinstance(parsed, list):
                blocks.extend(parsed)
            elif isinstance(parsed, dict):
                blocks.append(parsed)
        except yaml.YAMLError:
            pass  # Malformed blocks are silently skipped; logged via span
    return blocks
```

**Step 1.2 — Add `parse_adr_state()` helper**

```python
def parse_adr_state(content: str) -> str:
    """Extract ADR state from ## State section. Returns 'UNKNOWN' if not found."""
    match = re.search(r"^## State\s*\n+\s*(\S+)", content, re.MULTILINE)
    return match.group(1).strip() if match else "UNKNOWN"
```

**Step 1.3 — Add `load_exception_records()` helper**

Load EXC-* files from `.agent/adrs/` to support violation suppression:

```python
def load_exception_records(adrs_dir: Path) -> List[Dict[str, Any]]:
    """Load ACCEPTED exception records (EXC-*) for violation suppression."""
    exceptions = []
    for exc_file in sorted(adrs_dir.glob("EXC-*.md")):
        content = exc_file.read_text(errors="ignore")
        state = parse_adr_state(content)
        if state == "ACCEPTED":
            exceptions.append({
                "id": exc_file.stem,
                "content": content,
                "path": exc_file,
            })
    return exceptions
```

**Step 1.4 — Implement `run_adr_enforcement()` function**

Core enforcement engine. Follows `run_linter` pattern (line 135–203) with OTel span:

```python
def run_adr_enforcement(
    files: Optional[List[str]] = None,
    repo_root: Optional[Path] = None,
) -> bool:
    """Run ADR enforcement lint checks against files in scope.
    
    Args:
        files: Optional list of files to check (if None, checks all in-scope files)  
        repo_root: Repository root path (defaults to config.repo_root)
    
    Returns:
        True if no violations found, False otherwise.
    """
    from agent.core.config import config
    
    root = repo_root or config.repo_root
    adrs_dir = root / ".agent" / "adrs"
    
    if not adrs_dir.exists():
        console.print("[dim]⚠️  No ADRs directory found, skipping ADR enforcement.[/dim]")
        return True
    
    with tracer.start_as_current_span("lint.adr_enforcement") as span:
        # 1. Load all ACCEPTED ADRs with enforcement blocks
        rules = []
        for adr_file in sorted(adrs_dir.glob("ADR-*.md")):
            content = adr_file.read_text(errors="ignore")
            state = parse_adr_state(content)
            if state != "ACCEPTED":
                continue
            
            blocks = parse_adr_enforcement_blocks(content)
            adr_id = adr_file.stem.split("-")[0] + "-" + adr_file.stem.split("-")[1]
            for block in blocks:
                if block.get("type") == "lint":
                    rules.append({
                        "adr_id": adr_id,
                        "adr_file": adr_file.name,
                        "pattern": block.get("pattern", ""),
                        "scope": block.get("scope", "**/*"),
                        "message": block.get("violation_message", "ADR violation"),
                    })
        
        span.set_attribute("adr_count", len(list(adrs_dir.glob("ADR-*.md"))))
        span.set_attribute("rule_count", len(rules))
        
        if not rules:
            console.print("[dim]No ADR enforcement rules found.[/dim]")
            return True
        
        # 2. Load exception records
        exceptions = load_exception_records(adrs_dir)
        
        # 3. Apply rules
        violations = []
        
        for rule in rules:
            # Validate scope is relative
            scope = rule["scope"]
            if Path(scope).is_absolute():
                console.print(f"[red]❌ {rule['adr_id']}: Invalid absolute scope '{scope}'[/red]")
                violations.append({
                    "file": rule["adr_file"],
                    "line": 0,
                    "col": 0,
                    "message": f"{rule['adr_id']}: Invalid absolute scope '{scope}'",
                })
                continue
            
            # Resolve scope glob against repo root
            scope_path = root / scope
            matched_files = list(root.glob(scope))
            
            # If explicit file list given, intersect with scope
            if files:
                file_set = {str(Path(f).resolve()) for f in files}
                matched_files = [f for f in matched_files if str(f.resolve()) in file_set]
            
            # Compile pattern with timeout
            try:
                compiled = re.compile(rule["pattern"])
            except re.error as e:
                console.print(f"[red]❌ {rule['adr_id']}: Invalid regex '{rule['pattern']}': {e}[/red]")
                violations.append({
                    "file": rule["adr_file"],
                    "line": 0,
                    "col": 0,
                    "message": f"{rule['adr_id']}: Invalid regex: {e}",
                })
                continue
            
            for target_file in matched_files:
                if not target_file.is_file():
                    continue
                
                try:
                    content = target_file.read_text(errors="ignore")
                except Exception:
                    continue
                
                # Apply regex with SIGALRM timeout (5s)
                timed_out = False
                
                def _timeout_handler(signum, frame):
                    raise TimeoutError("Regex timeout")
                
                old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
                try:
                    signal.alarm(5)
                    for line_num, line in enumerate(content.splitlines(), 1):
                        match = compiled.search(line)
                        if match:
                            # Check if suppressed by an exception record
                            rel_path = str(target_file.relative_to(root))
                            suppressed = _is_suppressed_by_exception(
                                rule["adr_id"], rel_path, rule["pattern"], exceptions
                            )
                            if not suppressed:
                                violations.append({
                                    "file": rel_path,
                                    "line": line_num,
                                    "col": match.start() + 1,
                                    "message": f"{rule['adr_id']}: {rule['message']}",
                                })
                except TimeoutError:
                    timed_out = True
                    violations.append({
                        "file": rule["adr_file"],
                        "line": 0,
                        "col": 0,
                        "message": f"{rule['adr_id']}: Regex timed out for pattern '{rule['pattern']}'",
                    })
                finally:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)
        
        # 4. Report results
        span.set_attribute("violation_count", len(violations))
        span.set_attribute("exception_count", len(exceptions))
        
        if violations:
            console.print(f"\n[bold red]❌ ADR Enforcement: {len(violations)} violation(s) found[/bold red]")
            for v in violations:
                console.print(f"  {v['file']}:{v['line']}:{v['col']}: {v['message']}")
            span.set_attribute("status", "failed")
            return False
        else:
            console.print("[green]✅ ADR Enforcement: No violations found.[/green]")
            span.set_attribute("status", "success")
            return True


def _is_suppressed_by_exception(
    adr_id: str, file_path: str, pattern: str, exceptions: List[Dict]
) -> bool:
    """Check if a violation is suppressed by an ACCEPTED exception record."""
    for exc in exceptions:
        content = exc["content"]
        # Check if exception references this ADR and file
        if adr_id in content and file_path in content:
            return True
    return False
```

**Step 1.5 — Add `--adr-only` flag to `lint()` command**

Modify the existing [lint()](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/commands/lint.py#L322-L380) function:

```diff
 def lint(
     path: Optional[Path] = typer.Argument(
         None, help="Path to file or directory to lint."
     ),
     all_files: bool = typer.Option(
         False, "--all", help="Lint all files in the current directory recursively."
     ),
     base: str = typer.Option(
         None, "--base", help="Lint files changed relative to this base branch."
     ),
     staged: bool = typer.Option(
         True,
         "--staged/--no-staged",
         help="Lint staged files only (default if no path/all).",
     ),
     fix: bool = typer.Option(
         False, "--fix", help="Automatically fix lint errors where possible."
     ),
+    adr_only: bool = typer.Option(
+        False, "--adr-only", help="Run only ADR enforcement checks."
+    ),
 ):
```

```diff
+    if adr_only:
+        if not run_adr_enforcement(files=files):
+            console.print("[bold red]ADR enforcement failed.[/bold red]")
+            raise typer.Exit(1)
+        else:
+            console.print("[bold green]ADR enforcement passed.[/bold green]")
+        return
+
     # ... existing linter dispatch (ruff, shellcheck, eslint, markdownlint) ...
+
+    # Always run ADR enforcement at the end
+    if not run_adr_enforcement(files=files):
+        success = False
```

### Phase 2: Preflight Integration

#### [MODIFY] [check.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/commands/check.py)

**Step 2.1 — Add ADR Enforcement section to `preflight()`**

Insert a new section **after** the test execution block (line ~444) and **before** the AI governance panel:

```python
# --- ADR Enforcement (Deterministic Gate) ---
console.print("\n[bold blue]📐 Running ADR Enforcement Checks...[/bold blue]")
from agent.commands.lint import run_adr_enforcement

# Use staged files list if available
staged_files_for_adr = [str(f) for f in files] if files else None
adr_passed = run_adr_enforcement(files=staged_files_for_adr)

if not adr_passed:
    console.print("[bold red]❌ ADR Enforcement FAILED — violations must be fixed before merge.[/bold red]")
    if report_file:
        json_report["adr_enforcement"] = "FAIL"
    if not interactive:
        raise typer.Exit(code=1)
else:
    console.print("[green]✅ ADR Enforcement passed.[/green]")
    if report_file:
        json_report["adr_enforcement"] = "PASS"
```

### Phase 3: ADR-025 Verification

#### [VERIFY] [ADR-025-lazy-ai-service-initialization.md](file:///Users/jcook/repo/agentic-dev/.agent/adrs/ADR-025-lazy-ai-service-initialization.md)

ADR-025 **already contains** the canonical enforcement block at lines 41–51. No modification needed. The parser must handle:

```enforcement
- type: lint
  pattern: "^from agent\\.core\\.ai import ai_service"
  scope: "agent/commands/*.py"
  violation_message: "ADR-025: Do not import ai_service at module scope..."

- type: lint
  pattern: "^ai_service\\s*=\\s*AIService\\(\\)"  
  scope: "agent/commands/*.py"
  violation_message: "ADR-025: Do not instantiate AIService at module scope..."
```

**Note**: The scope `agent/commands/*.py` is relative to repo root. The glob resolution must handle `.agent/src/agent/commands/*.py` correctly — this may require the scope to be updated to `.agent/src/agent/commands/*.py` or the glob to search from the correct base path.

## Verification Plan

### Automated Tests

- [ ] Test 1: **Unit — `parse_adr_enforcement_blocks()`**: Valid YAML list, single dict, malformed YAML, missing block, multiple blocks in one ADR.
- [ ] Test 2: **Unit — `parse_adr_state()`**: ACCEPTED, DRAFT, SUPERSEDED, missing State section → UNKNOWN.
- [ ] Test 3: **Unit — Regex matching**: Pattern match on target line, no false positives on adjacent lines.
- [ ] Test 4: **Unit — Timeout**: Craft a catastrophic backtracking regex, assert `TimeoutError` is caught and reported as violation (not crash).
- [ ] Test 5: **Unit — Scope validation**: Absolute path rejected. Relative glob resolves correctly against repo root.
- [ ] Test 6: **Unit — `_is_suppressed_by_exception()`**: Exception record with matching ADR ID + file path suppresses. Non-matching does not.
- [ ] Test 7: **Integration — ADR-025**: Create temp file at `agent/commands/test_bad.py` with `from agent.core.ai import ai_service` at module scope → assert violation reported. Remove → assert clean.
- [ ] Test 8: **Integration — Status filtering**: DRAFT ADR enforcement block produces zero violations.
- [ ] Test 9: **Integration — `--adr-only` flag**: `env -u VIRTUAL_ENV uv run agent check lint --adr-only` runs only ADR enforcement, not ruff/eslint.
- [ ] Test 10: **Integration — Preflight**: `env -u VIRTUAL_ENV uv run agent preflight --skip-tests --ai=false` shows "ADR Enforcement" section.

### Manual Verification

- [ ] Step 1: Run `env -u VIRTUAL_ENV uv run agent check lint --adr-only` in the repo — verify ADR-025 rules execute against `agent/commands/*.py`.
- [ ] Step 2: Introduce a deliberate violation (module-scope `ai_service` import) and verify structured output.
- [ ] Step 3: Run `env -u VIRTUAL_ENV uv run agent preflight` and verify the ADR Enforcement section appears before the AI panel.

## Rollback Plan

1. Revert the `lint.py` and `check.py` changes (single commit revert).
2. ADR-025 enforcement block is read-only; no ADR modifications needed.
3. No database or config migrations — rollback is purely code revert.

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated with INFRA-057 entry
- [ ] README.md updated if CLI help text changes

### Observability

- [ ] `lint.adr_enforcement` OTel span added with `adr_count`, `rule_count`, `violation_count`, `exception_count` attributes
- [ ] Structured output uses `file:line:col: ADR-NNN message` format

### Testing

- [ ] Unit tests passed (10 test cases)
- [ ] Integration tests passed (4 test cases)
- [ ] Manual verification completed (3 steps)
