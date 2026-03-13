# STORY-ID: INFRA-110: Complete check.py decomposition to LOC ceiling

## State

COMMITTED

## Goal Description

Decompose the remaining logic in `.agent/src/agent/commands/check.py` into the `.agent/src/agent/core/check/` domain to satisfy the ADR-041 500 LOC maintainability ceiling. This move transitions `commands/check.py` from a monolithic orchestration script into a clean Typer-based CLI facade. The core logic for Impact Analysis, Governance Council orchestration, and Preflight reporting will be encapsulated in specialized modules, ensuring strict typing via `TypedDict` and preserving all behavioral contracts established in INFRA-103.

## Linked Journeys

- JRN-036: Preflight Governance Check
- JRN-057: Impact Analysis Workflow
- JRN-062: Implement Oracle Preflight Pattern

## Panel Review Findings

### @Architect
- **Compliance**: This story is the final step for ADR-041 compliance for the `check` command. 
- **Design**: Moving orchestration logic to `core/check/preflight.py` correctly separates CLI concerns (Rich, Typer) from business logic (Council orchestration).
- **ADR Checklist**: No new ADRs needed as this follows the existing pattern from INFRA-103.

### @Qa
- **Test Strategy**: The Test Impact Matrix identifies critical patch targets. Since we are moving logic that uses `subprocess.run` and `convene_council_full`, we must ensure tests are updated to patch the new module paths (e.g., `agent.core.check.preflight.subprocess` instead of `agent.commands.check.subprocess`).
- **Coverage**: New unit tests must be created for `core/check/preflight.py` and `core/check/impact.py`.

### @Security
- **PII Protection**: Ensure `scrub_sensitive_data` remains applied to all LLM-bound prompts (diffs, story content) in the new modules.
- **Secrets**: No API keys or credentials should be logged; only the presence/absence of tokens should be reported.

### @Product
- **User Impact**: The TUI output (Rich panels, progress markers) must remain identical. Users should not notice a change in the `agent preflight` or `agent impact` commands other than improved reliability.

### @Observability
- **Structured Logging**: Ensure truncation limits (from AC-5/INFRA-103) are logged using the structured `extra=` pattern in the new core modules.
- **OTEL**: Preserve trace spans for the preflight flow.

### @Docs
- **Accuracy**: No changes to the CLI API surface (commands/arguments) are planned, so user-facing documentation remains valid. Internal developer docs for `core/check` should be updated.

### @Compliance
- **Licensing**: All new files in `.agent/src/agent/core/check/` must include the standard Copyright 2026 Justin Cook header.

### @Mobile
- *N/A (CLI focus)*

### @Web
- *N/A (CLI focus)*

### @Backend
- **Type Safety**: Moving from `dict` to `TypedDict` for `ImpactResult` and `PreflightResult` is required to meet AC-2.
- **API Integrity**: The `preflight` function signature must remain compatible with existing callers in `workflow.py`.

## Codebase Introspection

### Target File Signatures (from source)

```python
# .agent/src/agent/commands/check.py
def _print_reference_summary(console: Console, roles_data: list, ref_metrics: dict, finding_validation: dict | None = None) -> None: ...
def on_thought(thought: str, step: int): ...
def on_tool_call(tool: str, args: dict, step: int): ...

# .agent/src/agent/core/check/system.py
def validate_linked_journeys(story_id: str, story_content: str) -> ValidateStoryResult: ...

# .agent/src/agent/core/check/quality.py
def check_journey_coverage(story_id: str) -> JourneyCoverageResult: ...
```

### Test Impact Matrix

| Test File | Current Patch Target | New Patch Target | Action Required |
|-----------|---------------------|-----------------|-----------------|
| `.agent/tests/commands/test_check_commands.py` | `agent.commands.check.subprocess.run` | `agent.core.check.impact.subprocess.run` | Update Patch |
| `.agent/tests/commands/test_panel.py` | `agent.commands.check.convene_council_full` | `agent.core.check.governance.convene_council_full` | Update Patch |
| `.agent/tests/integration/test_preflight_report.py` | `agent.commands.check.validate_story` | `agent.core.check.system.validate_story` | Update Patch |
| `.agent/tests/integration/test_python_agent.py` | `agent.commands.check.validate_story` | `agent.core.check.system.validate_story` | Update Patch |

### Behavioral Contracts

| Contract | Source | Current Value | Preserve? |
|----------|--------|--------------|-----------|
| Governance Temperature | INFRA-103 | `0.0` | YES |
| Truncation Limits | INFRA-103 | 200k (Vertex), 6k (GH), 40k (Default) | YES |
| Previous Verdicts Injection | INFRA-103 | Reads `.preflight_result` | YES |
| Deterministic Response | INFRA-103 | `SCOPE RULES` in system prompts | YES |

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Remove unused `re`, `subprocess`, and `json` imports from `commands/check.py` once logic is moved.
- [ ] Refactor `on_thought` and `on_tool_call` into a shared `core/check/ui_adapters.py` if they are reused between `impact` and `preflight`.

## Implementation Steps

### Step 1: Define shared models for check results

#### [NEW] .agent/src/agent/core/check/models.py

```python
"""
Copyright 2026 Justin Cook
Data models for check operations.
"""
from typing import Dict, List, Optional, TypedDict

class ImpactResult(TypedDict):
    story_id: str
    impact_summary: str
    changed_files: List[str]
    reverse_dependencies: Dict[str, List[str]]
    risk_assessment: str
    tokens_used: int

class RoleVerdict(TypedDict):
    role: str
    verdict: str  # PASS, BLOCK, NEUTRAL
    findings: List[str]
    citations: List[str]

class PreflightResult(TypedDict):
    story_id: str
    success: bool
    verdicts: List[RoleVerdict]
    impact: ImpactResult
    system_validation: Dict[str, Any]
    quality_metrics: Dict[str, Any]
    timestamp: str
```

### Step 2: Extract Impact Analysis logic

#### [NEW] .agent/src/agent/core/check/impact.py

```python
"""
Copyright 2026 Justin Cook
Core logic for impact analysis.
"""
import subprocess
from pathlib import Path
from typing import List, Optional
from agent.core.logger import get_logger
from agent.core.ai.prompts import generate_impact_prompt
from agent.core.ai.llm_service import ai_service
from agent.core.dependency_analyzer import DependencyAnalyzer
from agent.core.utils import scrub_sensitive_data
from agent.core.check.models import ImpactResult

logger = get_logger(__name__)

def run_impact_analysis(story_id: str, story_content: str, base_branch: str = "main") -> ImpactResult:
    """Performs static and AI-driven impact analysis."""
    # 1. Identify changes
    diff = subprocess.check_output(["git", "diff", f"{base_branch}...HEAD"]).decode()
    changed_files = _get_changed_files(base_branch)
    
    # 2. Dependency Analysis
    analyzer = DependencyAnalyzer()
    rev_deps = {f: analyzer.get_reverse_dependencies(f) for f in changed_files}
    
    # 3. AI Risk Assessment
    prompt = generate_impact_prompt(story_content, diff, rev_deps)
    assessment = ai_service.complete(scrub_sensitive_data(prompt))
    
    return {
        "story_id": story_id,
        "impact_summary": assessment,
        "changed_files": changed_files,
        "reverse_dependencies": rev_deps,
        "risk_assessment": assessment,
        "tokens_used": 0 # Placeholder for actual token counting
    }

def _get_changed_files(base: str) -> List[str]:
    files = subprocess.check_output(["git", "diff", "--name-only", f"{base}...HEAD"]).decode()
    return [f.strip() for f in files.split("\n") if f.strip()]
```

### Step 3: Extract Preflight Orchestration

#### [NEW] .agent/src/agent/core/check/preflight.py

```python
"""
Copyright 2026 Justin Cook
Preflight governance orchestration.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
from agent.core.logger import get_logger
from agent.core.governance import convene_council_full
from agent.core.check.models import PreflightResult, RoleVerdict
from agent.core.check.system import validate_linked_journeys
from agent.core.check.quality import check_journey_coverage
from agent.core.check.impact import run_impact_analysis

logger = get_logger(__name__)

def execute_preflight(story_id: str, story_content: str) -> PreflightResult:
    """Orchestrates the full preflight check sequence."""
    # 1. System & Quality Checks
    sys_val = validate_linked_journeys(story_id, story_content)
    quality = check_journey_coverage(story_id)
    
    # 2. Impact Analysis
    impact = run_impact_analysis(story_id, story_content)
    
    # 3. Governance Council
    previous_verdicts = _load_previous_verdicts()
    verdicts = convene_council_full(
        story_content=story_content,
        diff=_get_current_diff(),
        previous_verdicts=previous_verdicts
    )
    
    success = all(v["verdict"] != "BLOCK" for v in verdicts)
    
    result: PreflightResult = {
        "story_id": story_id,
        "success": success,
        "verdicts": verdicts,
        "impact": impact,
        "system_validation": sys_val,
        "quality_metrics": quality,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    _persist_result(result)
    return result

def _load_previous_verdicts() -> str:
    path = Path(".preflight_result")
    if path.exists():
        return path.read_text()
    return ""

def _persist_result(result: PreflightResult) -> None:
    Path(".preflight_result").write_text(json.dumps(result, indent=2))

def _get_current_diff() -> str:
    import subprocess
    return subprocess.check_output(["git", "diff", "HEAD"]).decode()
```

### Step 4: Refactor commands/check.py into a thin facade

#### [MODIFY] .agent/src/agent/commands/check.py

```
<<<SEARCH
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional
from agent.core.logger import get_logger
import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm  # Needed now for UI logic
from rich.panel import Panel
import os
from agent.core.ai.prompts import generate_impact_prompt
from agent.core.config import config
from agent.core.context import context_loader
from agent.core.governance import convene_council_full
from agent.core.utils import infer_story_id, scrub_sensitive_data
from agent.core.fixer import InteractiveFixer
from agent.core.check.quality import check_journey_coverage  # noqa: F401
from agent.core.check.system import validate_linked_journeys  # noqa: F401
===
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from agent.core.config import config
from agent.core.utils import infer_story_id
from agent.core.check.preflight import execute_preflight
from agent.core.check.impact import run_impact_analysis
from agent.core.check.system import validate_linked_journeys
>>>
<<<SEARCH
@app.command()
def preflight(
    story: Optional[str] = typer.Option(None, "--story", "-s", help="Story ID"),
    # ... other params ...
):
    # (Existing 1,000 lines of logic)
===
@app.command()
def preflight(
    story: Optional[str] = typer.Option(None, "--story", "-s", help="Story ID"),
    legacy_context: bool = typer.Option(False, "--legacy-context", help="Use legacy full-context prompt"),
):
    """Run governance preflight checks."""
    console = Console()
    story_id = story or infer_story_id()
    
    with console.status(f"[bold green]Running preflight for {story_id}...", spinner="dots"):
        # We assume story_content is loaded here or within execute_preflight
        from agent.core.context import context_loader
        story_content = context_loader.load_story(story_id)
        
        result = execute_preflight(story_id, story_content)
    
    # Output formatting using thin wrappers
    _render_preflight_report(console, result)
    
    if not result["success"]:
        raise typer.Exit(code=1)

def _render_preflight_report(console: Console, result: Any):
    # Minimal formatting logic remains or moved to core/check/report.py
    console.print(Panel(f"Preflight Result: {'PASS' if result['success'] else 'BLOCK'}", 
                        style="bold green" if result["success"] else "bold red"))
>>>
```

## Verification Plan

### Automated Tests

- [ ] `pytest .agent/tests/core/check/test_preflight.py` (New unit tests for extracted logic)
- [ ] `pytest .agent/tests/commands/test_check_commands.py` (Ensure facade delegation works)
- [ ] `pytest .agent/tests/integration/test_preflight_report.py` (End-to-end output verification)

### Manual Verification

- [ ] Run `agent preflight --story INFRA-110`. 
    - Expected: Council convenes, impact analysis runs, `.preflight_result` is written, and the console output is formatted as before.
- [ ] Run `agent impact --story INFRA-110`.
    - Expected: AI-powered risk assessment is displayed.

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated: "Completed decomposition of `check.py` to meet ADR-041 LOC ceiling."
- [ ] Internal documentation for `agent.core.check` updated in `.agent/docs/architecture/domain-check.md`.

### Observability

- [ ] Truncation logs contain `extra={"provider": "...", "limit": ...}`.
- [ ] `execute_preflight` span is visible in OTEL traces.

### Testing

- [ ] All existing tests pass (with updated patch targets).
- [ ] 100% branch coverage on `.agent/src/agent/core/check/impact.py`.

## Copyright

Copyright 2026 Justin Cook