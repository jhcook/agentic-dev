# STORY-ID: INFRA-106: Enforce LOC Ceiling via CI and Documentation

## State

ACCEPTED

## Goal Description

Establish automated technical controls to enforce the 500 Lines of Code (LOC) ceiling and import hygiene standards defined in ADR-041. This prevents the re-emergence of monolithic "God Objects" by integrating static analysis checks into the `agent preflight` pipeline and pre-commit hooks, ensuring the architectural decomposition remains self-sustaining.

## Linked Journeys

- JRN-036: Preflight Governance Check
- JRN-057: Impact Analysis Workflow

## Panel Review Findings

### @Architect
- **Review**: The plan correctly formalizes ADR-041 into technical gates. Using `ast` for static analysis ensures we don't hit runtime circularity issues while checking for them.
- **Check**: ADR-041 is being updated to clarify "Physical Lines", which is the correct metric for file-level complexity management.

### @Qa
- **Review**: The test strategy covers synthetic fixtures for LOC violations and circular dependencies (direct and transitive).
- **Check**: Ensure `tests/scripts/` is added to the tree for these new verification scripts.

### @Security
- **Review**: The scripts strictly use `ast` and avoid `importlib`, preventing arbitrary code execution during analysis. The 10MB file size limit and `follow_symlinks=False` are critical for DoS and path traversal protection.
- **Check**: No PII in logs is enforced by logging relative paths only.

### @Product
- **Review**: The acceptance criteria are clear and the "Exceptions Process" allows for pragmatic handling of edge cases (like migrations).
- **Check**: The `agent preflight` output will now include "LOC Ceiling" as a explicit gate, improving developer feedback.

### @Observability
- **Review**: Wiring the checks into `core/check/quality.py` with OpenTelemetry attributes (`code.quality.loc_max`, `code.quality.violation_count`) provides long-term metrics on codebase health.
- **Check**: Ensure the `GateResult` integrates with existing telemetry spans in `commands/check.py`.

### @Docs
- **Review**: ADR-041, README, and CHANGELOG are all slated for updates. 
- **Check**: Documentation includes the command to reproduce failures locally.

### @Compliance
- **Review**: License headers are required for the new scripts. GDPR data minimization is respected by avoiding absolute paths in logs.
- **Check**: Lawful basis for data processing is not applicable here as these are internal developer tools with no user PII.

### @Backend
- **Review**: Using Python standard library (`ast`, `pathlib`) keeps the maintenance burden low and supply chain surface small.
- **Check**: The `check_imports.py` script must correctly resolve relative imports to detect cross-package circularity.

## Codebase Introspection

### Targeted File Contents (from source)

(Introspection of `agent/commands/check.py` and `agent/core/check/quality.py` confirms entry points for new gates.)

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| `tests/commands/test_check_commands.py` | `agent.commands.check.subprocess.run` | `agent.commands.check.check_code_quality` | Add test case for quality gate failure. |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| `agent preflight` exit code | CLI logic | Non-zero on any gate failure | Yes |
| Static analysis safety | ADR-041 | No code execution for metadata | Yes |

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Remove any leftover manual LOC comments in `agent/core/context.py` if present.

## Implementation Steps

### Step 1: Create LOC Ceiling Check Script

#### [NEW] scripts/check_loc.py

```python
#!/usr/bin/env python3
"""
Copyright 2026 Justin Cook
License: Apache-2.0
Enforce 500 physical LOC ceiling on Python files.
"""
import ast
import json
import os
import sys
from pathlib import Path
from typing import List, Tuple

MAX_LOC = 500
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def is_exempt(path: Path, content: str) -> bool:
    if "migrations/" in str(path):
        return True
    if "# nolint: loc-ceiling" in content:
        return True
    return False

def check_file(path: Path) -> Tuple[int, bool]:
    if path.stat().st_size > MAX_FILE_SIZE:
        return 0, False
    try:
        content = path.read_text(encoding="utf-8")
        if is_exempt(path, content):
            return 0, True
        lines = content.splitlines()
        return len(lines), len(lines) <= MAX_LOC
    except (UnicodeDecodeError, PermissionError):
        return 0, True

def main():
    root = Path(".agent/src/agent")
    if not root.exists():
        root = Path("src/agent")
    
    violations = []
    for p in root.rglob("*.py"):
        if p.is_symlink(): continue
        count, ok = check_file(p)
        if not ok:
            violations.append({"file": str(p), "loc": count})

    if "--format" in sys.argv and "json" in sys.argv:
        print(json.dumps(violations))
    else:
        for v in violations:
            print(f"FAIL: {v['file']} exceeds 500 LOC ({v['loc']}). Fix: agent preflight --gate quality")
    
    sys.exit(1 if violations else 0)

if __name__ == "__main__":
    main()
```

### Step 2: Create Import Hygiene Check Script

#### [NEW] scripts/check_imports.py

```python
#!/usr/bin/env python3
"""
Copyright 2026 Justin Cook
License: Apache-2.0
Detect circular dependencies using static AST analysis.
"""
import ast
import sys
from pathlib import Path
from typing import Dict, Set, List

def get_imports(path: Path) -> Set[str]:
    imports = set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    imports.add(n.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split('.')[0])
    except Exception:
        pass
    return imports

def find_cycle(graph: Dict[str, Set[str]]):
    visited = set()
    path = []
    
    def visit(node):
        if node in path:
            return path[path.index(node):] + [node]
        if node in visited:
            return None
        visited.add(node)
        path.append(node)
        for neighbor in graph.get(node, []):
            res = visit(neighbor)
            if res: return res
        path.pop()
        return None

    for node in graph:
        res = visit(node)
        if res: return res
    return None

def main():
    root = Path("src/agent") if Path("src/agent").exists() else Path(".agent/src/agent")
    graph = {}
    for p in root.rglob("*.py"):
        mod = p.stem
        graph[mod] = get_imports(p)
    
    cycle = find_cycle(graph)
    if cycle:
        print(f"FAIL: Circular dependency detected: {' -> '.join(cycle)}")
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
```

#### [MODIFY] .agent/src/agent/core/check/quality.py

```
<<<SEARCH
def check_journey_coverage(filepaths: List[Path]) -> GateResult:
===
from agent.commands.gates import GateResult
import subprocess

def check_code_quality() -> GateResult:
    """Run LOC and Import checks."""
    loc_res = subprocess.run(["python3", "scripts/check_loc.py"], capture_output=True, text=True)
    import_res = subprocess.run(["python3", "scripts/check_imports.py"], capture_output=True, text=True)
    
    success = loc_res.returncode == 0 and import_res.returncode == 0
    message = (loc_res.stdout + import_res.stdout).strip() or "All quality checks passed."
    
    return GateResult(
        gate_name="Code Quality",
        success=success,
        message=message,
        metrics={
            "code.quality.violation_count": 0 if success else 1,
            "code.quality.loc_max": 500
        }
    )

def check_journey_coverage(filepaths: List[Path]) -> GateResult:
>>>
```

### Step 4: Integrate Gate into Preflight Command

#### [MODIFY] .agent/src/agent/commands/check.py

```
<<<SEARCH
from agent.core.check.quality import check_journey_coverage  # noqa: F401
===
from agent.core.check.quality import check_journey_coverage, check_code_quality
>>>
<<<SEARCH
@app.command()
def preflight(
    story_id: Optional[str] = typer.Option(None, "--story"),
===
@app.command()
def preflight(
    story_id: Optional[str] = typer.Option(None, "--story"),
    gate: Optional[str] = typer.Option(None, "--gate"),
) -> None:
    # ... logic to filter by gate if provided ...
    if not gate or gate == "quality":
        res = check_code_quality()
        if not res.success:
            Console().print(f"[red]Quality Gate Failed:[/red] {res.message}")
            raise typer.Exit(code=1)
>>>
```

### Step 5: Configure Pre-commit Hook

#### [NEW] .pre-commit-config.yaml

```yaml
repos:
-   repo: local
    hooks:
    -   id: check-loc
        name: Enforce 500 LOC Ceiling
        entry: python3 scripts/check_loc.py
        language: system
        files: ^src/agent/.*\.py$
        pass_filenames: false
    -   id: check-imports
        name: Detect Circular Imports
        entry: python3 scripts/check_imports.py
        language: system
        files: ^src/agent/.*\.py$
        pass_filenames: false
```

### Step 6: Update Documentation and ADR

#### [MODIFY] docs/adr/ADR-041-module-decomposition.md

```
<<<SEARCH
## Standards
Files should be kept small.
===
## Standards
- **LOC Ceiling**: No Python file in `src/agent/` shall exceed 500 physical lines.
- **Metric**: "Physical Lines" includes all lines in the file (code, comments, whitespace).
- **Exceptions**: Database migrations and generated files are exempt. Manual exceptions can be granted via `# nolint: loc-ceiling`.
- **Enforcement**: Checked via `scripts/check_loc.py` in CI and pre-commit hooks.
>>>
```

#### [MODIFY] README.md

```
<<<SEARCH
## Development
===
## Development

### Code Quality
We enforce a 500 LOC ceiling per file and circular dependency checks.
To run locally:
```bash
agent preflight --gate quality
# OR
python3 scripts/check_loc.py
python3 scripts/check_imports.py
```
>>>

## Verification Plan

### Automated Tests
- [ ] `pytest tests/scripts/test_check_loc.py`: Verify violation detection and exemption logic.
- [ ] `pytest tests/scripts/test_check_imports.py`: Verify direct and transitive cycle detection.
- [ ] `agent preflight --gate quality`: Confirm it passes on the current clean codebase.

### Manual Verification
- [ ] Create `src/agent/oversized.py` with 501 lines. Run `agent preflight --gate quality`. Expected: Exit code 1 with "oversized.py exceeds 500 LOC".
- [ ] Create two files with circular imports. Run `scripts/check_imports.py`. Expected: Exit code 1 with cycle path.

## Definition of Done

### Documentation
- [ ] CHANGELOG.md updated with "Internal: Automated 500 LOC and circular import enforcement."
- [ ] ADR-041 updated.

### Observability
- [ ] `code.quality.*` attributes visible in preflight OTel spans.
- [ ] Logs show relative paths for violations.

### Testing
- [ ] Unit tests for new scripts added.
- [ ] Integration into `agent preflight` verified.

## Copyright

Copyright 2026 Justin Cook