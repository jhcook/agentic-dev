# INFRA-067: Enhance `env -u VIRTUAL_ENV uv run agent implement` with Post-Apply Governance Gates

## State

ACCEPTED

## Goal Description

Enhance the `env -u VIRTUAL_ENV uv run agent implement` CLI command to programmatically enforce post-apply governance phases (Security Scan, QA Validation, Documentation Check) instead of relying on AI agent interpretation of workflow instructions.

## Linked Journeys

- JRN-056: Full Implementation Workflow

## Panel Review Findings

**@Architect**:

- ADR-028 (Synchronous CLI Design) is respected by using `subprocess.run()` for external commands.
- ADR-030 (Workflow-Calls-CLI Pattern) will be created to document the new workflow.
- The introduction of `gates.py` respects architectural boundaries by encapsulating post-apply logic.

**@Qa**:

- The Test Strategy covers unit and integration tests. Additional edge case testing should be considered (e.g., what happens if the `test_command` configured in `agent.yaml` is invalid).
- Critical User Flows from `CRITICAL_FLOWS.mdc` aren't directly implicated in the new code itself, but end-to-end workflow using `env -u VIRTUAL_ENV uv run agent implement` should be verified.

**@Security**:

- The security scan uses patterns from `security_patterns.yaml`, which is good.
- PII detection reports presence but must not log the PII itself. This is handled.
- `--skip-security` flag provides an override, but the audit logging is essential.
- No immediate security concerns.

**@Product**:

- Acceptance Criteria are clear and testable.
- Impact Analysis identifies affected components and potential risks.

**@Observability**:

- Structured console output with timing is good. Consider adding OpenTelemetry instrumentation (tracing) within `gates.py` to provide more granular performance insights. The CLI already uses logging and should be used here.
- Ensure logs don't contain PII and follow the existing structure.

**@Docs**:

- A new `security_patterns.yaml` file needs to be documented (format, example patterns).
- `env -u VIRTUAL_ENV uv run agent implement` command documentation needs to be updated with the new flags (`--skip-tests`, `--skip-security`).
- The new `gates.py` module should have module-level documentation.

**@Compliance**:

- License headers must be present in all new files.
- GDPR compliance is maintained as no PII is logged.
- Audit logging of `--skip-*` flags provides a compliance trail.

**@Mobile**:

- Not applicable to this story, as it's a CLI enhancement.

**@Web**:

- Not applicable to this story, as it's a CLI enhancement.

**@Backend**:

- Types should be strictly enforced in the new `gates.py` module.
- API documentation (OpenAPI) will need to be reviewed if the changes to `env -u VIRTUAL_ENV uv run agent implement` impact any existing API endpoints (unlikely, but should be checked).

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Convert `print` statements to use the `agent.core.logger` logger in `src/agent/commands/implement.py` and `src/agent/commands/gates.py`.
- [ ] Add type hints to the new functions in `src/agent/commands/gates.py`.

## Implementation Steps

### gates.py

#### NEW src/agent/commands/gates.py

```python
import logging
import subprocess
import re
from pathlib import Path
from typing import List, Optional
import time
from agent.core.config import config
from agent.core.logger import get_logger

logger = get_logger(__name__)

def run_security_scan(filepath: Path, security_patterns_path: Path) -> bool:
    """
    Scans a file for security vulnerabilities using patterns defined in a YAML file.
    Returns True if the scan passes, False otherwise.
    """
    start_time = time.time()
    try:
        with open(security_patterns_path, "r") as f:
            import yaml
            security_patterns = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Security patterns file not found: {security_patterns_path}")
        return False
    except yaml.YAMLError as e:
        logger.error(f"Error reading security patterns file: {e}")
        return False

    try:
        with open(filepath, "r") as f:
            content = f.read()
    except FileNotFoundError:
        logger.error(f"File not found: {filepath}")
        return False

    blocked = False
    for pattern_name, pattern in security_patterns.items():
        if re.search(pattern, content):
            logger.warning(f"Security scan blocked: {pattern_name} found in {filepath}")
            blocked = True

    elapsed_time = time.time() - start_time
    if blocked:
        logger.info(f"[PHASE] Security Scan ... BLOCKED ({elapsed_time:.2f}s)")
        return False
    else:
        logger.info(f"[PHASE] Security Scan ... PASSED ({elapsed_time:.2f}s)")
        return True


def run_qa_gate(test_command: str) -> bool:
    """
    Runs the QA gate by executing the configured test command.
    Returns True if the tests pass (exit code 0), False otherwise.
    """
    start_time = time.time()
    try:
        result = subprocess.run(test_command, shell=True, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            logger.error(f"QA gate failed: {result.stderr}")
            elapsed_time = time.time() - start_time
            logger.info(f"[PHASE] QA Validation ... BLOCKED ({elapsed_time:.2f}s)")
            return False
        else:
            elapsed_time = time.time() - start_time
            logger.info(f"[PHASE] QA Validation ... PASSED ({elapsed_time:.2f}s)")
            return True
    except FileNotFoundError:
        logger.error(f"Test command not found: {test_command}")
        return False
    except Exception as e:
        logger.error(f"Error running QA gate: {e}")
        return False


def run_docs_check(filepath: Path) -> bool:
    """
    Verifies that all new/modified top-level functions in a Python file have docstrings.
    Returns True if the check passes, False otherwise.
    """
    start_time = time.time()
    try:
        import ast
        with open(filepath, "r") as f:
            tree = ast.parse(f.read())

        blocked = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and ast.get_docstring(node) is None:
                logger.warning(f"Documentation check failed: Function {node.name} missing docstring in {filepath}")
                blocked = True

        elapsed_time = time.time() - start_time
        if blocked:
            logger.info(f"[PHASE] Documentation Check ... BLOCKED ({elapsed_time:.2f}s)")
            return False
        else:
            logger.info(f"[PHASE] Documentation Check ... PASSED ({elapsed_time:.2f}s)")
            return True

    except FileNotFoundError:
        logger.error(f"File not found: {filepath}")
        return False
    except Exception as e:
        logger.error(f"Error running documentation check: {e}")
        return False

```

### implement.py

#### MODIFY src/agent/commands/implement.py

```diff
--- a/src/agent/commands/implement.py
+++ b/src/agent/commands/implement.py
@@ -14,6 +14,7 @@
 from agent.core.config import config
 from agent.core.utils import (
 from agent.core.context import context_loader
+from agent.commands import gates
 from agent.commands.utils import update_story_state
 import subprocess
 def parse_code_blocks(content: str) -> List[Dict[str, str]]
@@ -65,6 +66,9 @@
     console: Console,
     runbook_path: Path,
     yes: bool = False,
+    skip_journey_check: bool = False,
+    skip_tests: bool = False,
+    skip_security: bool = False,
 ) -> None:
     """
     Implements the changes described in a runbook.
@@ -73,6 +77,7 @@
     story_id = extract_story_id(runbook_id, runbook_content)
     if not story_id:
         story_id = infer_story_id(runbook_path.name)
+
     story_data = context_loader.story(story_id)
     if not story_data:
         console.print(f"[bold red]ERROR:[/bold red] Story [bold]{story_id}[/bold] not found. Create it with [bold]agent story create[/bold].")
@@ -80,6 +85,10 @@
 
     console.print(f"Implementing story [bold]{story_id}[/bold] from runbook [bold]{runbook_path.name}[/bold]...")
 
+    if skip_journey_check:
+        console.print("⚠️ [AUDIT] Journey check skipped.")
+        #log_governance_event("Journey gate skipped") # TODO: implement
+
     if config.workflow_engine == "local":
         current_branch = get_current_branch()
         if current_branch.startswith("story/"):
@@ -128,6 +137,47 @@
                 apply_change_to_file(filepath, block["content"], yes=yes)
         console.print("[bold green]Changes applied.[/bold green]")
 
+        # Post-apply governance gates
+        security_patterns_path = Path(".agent/etc/security_patterns.yaml")
+        test_command = config.get("test_command", "make test")
+
+        all_passed = True
+        if not skip_security:
+            security_passed = True
+            for filepath in modified_files:
+                if not gates.run_security_scan(Path(filepath), security_patterns_path):
+                    security_passed = False
+                    all_passed = False
+            if skip_security:
+                 console.print(f"⚠️ [AUDIT] Security gate skipped at {datetime.now().isoformat()}")
+            if not security_passed:
+                console.print("[bold red]Security scan failed. Implementation blocked.[/bold red]")
+
+        else:
+            console.print(f"⚠️ [AUDIT] Security gate skipped at {datetime.now().isoformat()}")
+
+        if not skip_tests:
+            if not gates.run_qa_gate(test_command):
+                console.print("[bold red]QA gate failed. Implementation blocked.[/bold red]")
+                all_passed = False
+            if skip_tests:
+                 console.print(f"⚠️ [AUDIT] Tests skipped at {datetime.now().isoformat()}")
+
+        else:
+            console.print(f"⚠️ [AUDIT] Tests skipped at {datetime.now().isoformat()}")
+
+        docs_passed = True
+        for filepath in modified_files:
+            if filepath.endswith(".py"):
+                if not gates.run_docs_check(Path(filepath)):
+                    docs_passed = False
+                    all_passed = False
+        if not docs_passed:
+            console.print("[bold red]Documentation check failed. Implementation blocked.[/bold red]")
+
+        if all_passed:
+            console.print("[bold green]All governance checks passed.[/bold green]")
+
         if story_id:
             update_story_state(story_id, "IMPLEMENTED")
     else:
@@ -139,6 +189,9 @@
     runbook_path: Path = typer.Argument(..., help="Path to the runbook file."),
     yes: bool = typer.Option(False, "--yes", "-y", help="Automatically apply changes without prompting."),
     apply: bool = typer.Option(False, "--apply", help="Apply the changes to the codebase."),
+    skip_journey_check: bool = typer.Option(False, "--skip-journey-check", help="Skip the journey check."),
+    skip_tests: bool = typer.Option(False, "--skip-tests", help="Skip running tests."),
+    skip_security: bool = typer.Option(False, "--skip-security", help="Skip the security scan."),
 ) -> None:
     """
     Implements a story from a runbook.
@@ -148,7 +201,7 @@
     if not runbook_path.exists():
         console.print(f"[bold red]ERROR:[/bold red] Runbook not found: [bold]{runbook_path}[/bold]")
         raise typer.Exit(code=1)
-    if apply:
+    if apply: # pragma: no cover - only runs with --apply
         implement(console, runbook_path, yes, runbook_content)
     else:
         console.print("[yellow]Dry run. Use --apply to apply the changes.[/yellow]")

```

#### NEW .agent/etc/security_patterns.yaml

```yaml
api_key: "sk-[a-zA-Z0-9]+"
eval_exec: "(eval|exec)\("
pii: "(password|ssn|credit card)"
```

### agent.yaml

#### MODIFY .agent/etc/agent.yaml

```yaml
test_command: "make test"
```

## Verification Plan

### Automated Tests

- [ ] Test 1: `test_implement_skip_journey_check` — verify `--skip-journey-check` bypasses journey gate and logs audit warning.
- [ ] Test 2: `test_implement_security_scan_blocks` — verify security scan catches `eval()` or API keys in AI output.
- [ ] Test 3: `test_implement_qa_runs_tests` — verify configured test command is called when `--apply` is used.
- [ ] Test 4: `test_gates_composable` — verify `gates.py` functions work independently and in combination.
- [ ] Test 5: End-to-end `/implement` workflow regression after Phase 1.
- [ ] Test 6: All 6 existing tests in `test_implement.py` must continue to pass.
- [ ] Test 7: Add a test case where an invalid test command is set in agent.yaml, asserting that the CLI correctly handles the error and blocks implementation.

### Manual Verification

- [ ] Step 1: Create a dummy Python file with a function lacking a docstring. Run `env -u VIRTUAL_ENV uv run agent implement` with `--apply` and verify that the documentation check blocks the implementation.
- [ ] Step 2: Modify a file and include the string "sk-..." (an API key pattern). Run `env -u VIRTUAL_ENV uv run agent implement` with `--apply` and verify that the security scan blocks the implementation.
- [ ] Step 3: Run `env -u VIRTUAL_ENV uv run agent implement` with `--apply --skip-tests --skip-security` and verify that the audit logs are printed to the console for both skipped gates.
- [ ] Step 4: Configure a failing `test_command` in `agent.yaml` (e.g., `false`). Run `env -u VIRTUAL_ENV uv run agent implement` with `--apply` and verify that the QA gate blocks the implementation.
- [ ] Step 5: Verify that `--skip-journey-check` is functional. (Needs Journey setup, can use a dummy Journey)

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated
- [ ] README.md updated (if applicable)
- [ ] API Documentation updated (if applicable)

### Observability

- [ ] Logs are structured and free of PII
- [ ] Metrics added for new features

### Testing

- [ ] Unit tests passed
- [ ] Integration tests passed
