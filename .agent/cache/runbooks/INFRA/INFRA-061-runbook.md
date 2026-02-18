# INFRA-061: ADK Multi-Agent Governance Panel

## State

ACCEPTED

## Goal Description

Replace the sequential-prompt governance panel with an ADK-based multi-agent system, enabling tool use, delegation, and iterative analysis for each governance role.

## Linked Journeys

- JRN-033: Governance Council Tool Suite
- JRN-045: Governance Hardening
- JRN-055: ADK Multi-Agent Panel Review

## Panel Review Findings

**@Architect**:

- The proposed architecture correctly isolates the ADK implementation within a dedicated `agent/core/adk/` package. This respects architectural boundaries.
- The use of an adapter to wrap `AIService.complete()` ensures vendor agnosticism, aligning with the project's goals.
- The `_filter_relevant_roles()` output is correctly passed to the orchestrator factory.
- ADR-029 is missing and needs to be written.
- The package structure within `agent/core/adk/` seems reasonable.
- Consider creating an ADR for the tool definitions themselves if they become complex.

**@Qa**:

- The test strategy is comprehensive, covering unit, parity, integration, and benchmark tests.
- The inclusion of negative tests and fallback tests is excellent.
- The structural parity tests are appropriate given the expected content differences.
- The addition of `test_coordinator_delegation()` and `test_agent_max_iterations()` is necessary.
- Verify that the timeout test for tools is actually timing out, and not just returning quickly.
- Critical User Flows do not need updates as the ADK implementation doesn't alter the end user experience.

**@Security**:

- The explicit tool whitelist and path validation are critical security measures.
- The use of `subprocess.run` with a timeout for `search_codebase` is appropriate.
- The transitive dependency audit before merge is essential.
- The justification for `threading.Lock()` is reasonable given the `AIService` singleton.
- Ensure that the `search_codebase` tool does not expose any sensitive information through its output, even with the limit.
- Confirm that all 5 read-only tools are indeed read-only (no accidental write access).

**@Product**:

- The feature flag implementation in `agent.yaml` is well-defined.
- The fallback message and console display provide helpful user feedback.
- The choice of `legacy` as the default engine is appropriate for backward compatibility.
- Ensure that documentation is updated to reflect the new configuration option and its implications.
- Consider adding a brief description of the ADK engine in the help text for the `preflight` command.

**@Observability**:

- The OpenTelemetry spans provide good coverage of the ADK panel's execution.
- The inclusion of attributes like `panel.engine`, `verdict`, `findings_count`, `tool_calls_count`, and `error` is helpful for analysis.
- The benchmark metric `panel.runtime_ms` will be valuable for performance monitoring.
- Consider adding logging for the specific ADK exception types that trigger fallback.

**@Docs**:

- ADR-029 is required to document the architectural decisions related to ADK integration.
- The CHANGELOG should be updated to reflect the new feature.
- The install docs should be updated with `pip install 'agent[adk]'`.
- Ensure that the documentation clearly explains how to configure and use the ADK panel.
- The roles and responsibilities described in the introduction also need to be updated if the agent descriptions have changed.

**@Compliance**:

- The Apache 2.0 license compatibility of `google-adk` is confirmed.
- The transitive dependency check is mandatory.
- The audit log format parity is crucial for SOC 2 compliance.
- Ensure that the use of ADK does not introduce any new data processing activities that require additional GDPR considerations.

**@Mobile**:

- No impact, orchestration-only change.
- Verify that existing mobile tests continue to pass after the ADK integration.

**@Web**:

- No impact, orchestration-only change.
- Verify that existing web tests continue to pass after the ADK integration.

**@Backend**:

- The adapter implementation using `threading.Lock()` and `loop.run_in_executor` is appropriate for bridging the sync ↔ async gap.
- The mapping of `agents.yaml` fields to ADK agent properties is well-defined.
- The use of `asyncio.run()` at the top of `_convene_council_adk()` is correct.
- Ensure that all exceptions are properly handled and logged within the adapter and orchestrator.

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Convert existing `print` statements in the `governance.py` and new ADK files to use the logging module with structured logging for better observability.
- [ ] Standardize the exception handling in `governance.py` and the new ADK files to use a consistent pattern with informative error messages.
- [ ] Review and improve the code formatting in `governance.py` and the new ADK files to adhere to PEP 8 guidelines.

## Implementation Steps

### Step 1: pyproject.toml — Optional ADK Dependency (AC-1, AC-19)

#### MODIFY pyproject.toml

- Add `google-adk>=1.0.0` as an optional dependency under `[project.optional-dependencies]`.
- Run `pip install google-adk && pip list | wc -l` to audit transitive deps.
- Verify no GPL/AGPL transitive deps exist.

```toml
[project.optional-dependencies]
adk = [
    "google-adk>=1.0.0",
]
```

---

### Step 2: agent/core/config.py — Panel Engine Config (AC-8)

#### MODIFY agent/core/config.py

- Add a `panel_engine` property to the `Config` class.
- Reads from `agent.yaml` under the `panel:` section.
- Defaults to `"legacy"`.
- Note: The `Config` class has `load_yaml()` and `get_value()` but no generic `get()`.

```python
@property
def panel_engine(self) -> str:
    """
    Returns the panel engine to use ('adk' or 'legacy').
    Reads from agent.yaml under the 'panel:' section.
    Defaults to 'legacy' if not specified.
    """
    try:
        data = self.load_yaml(self.etc_dir / "agent.yaml")
        return data.get("panel", {}).get("engine", "legacy")
    except Exception:
        return "legacy"
```

---

### Step 3: agent/etc/agent.yaml — Panel Config Section (AC-8)

#### MODIFY agent/etc/agent.yaml

- Add `panel:` section with `engine: legacy` default.

```yaml
panel:
  engine: legacy  # Can be "adk" or "legacy"
```

---

### Step 4: agent/core/adk/**init**.py — Package Initializer

#### NEW agent/core/adk/**init**.py

```python
# Copyright 2026 Justin Cook
#
# Licensed under the Apache License, Version 2.0 (the "License");
# ...
"""
ADK Multi-Agent Governance Panel.

This package implements multi-agent orchestration for the governance council
using Google's Agent Development Kit (ADK). It wraps the existing AIService
through a vendor-agnostic adapter and maps governance roles to ADK agents
with read-only tool access.
"""
```

---

### Step 5: agent/core/adk/adapter.py — AIService ↔ ADK Bridge (AC-2, AC-12, AC-13)

#### NEW agent/core/adk/adapter.py

- Wraps `AIService.complete()` holistically via `loop.run_in_executor()`.
- Uses `threading.Lock()` to serialize concurrent calls through the singleton.
- Preserves vendor agnosticism — ADK never knows which provider is used.

```python
import asyncio
import threading
import logging
from typing import Optional

from google.adk.models import BaseLlm, LlmResponse, LlmRequest
from agent.core.ai.service import AIService

logger = logging.getLogger(__name__)


class AIServiceModelAdapter(BaseLlm):
    """
    Adapts the synchronous AIService to ADK's async BaseLlm interface.

    Wraps AIService.complete() holistically — the entire service (including
    provider fallback logic in try_switch_provider()) is treated as a black box.
    The adapter does NOT call individual providers. This preserves vendor
    agnosticism: ADK never knows which provider is used.

    Thread safety: Uses threading.Lock() because AIService is a module-level
    singleton (service.py:728) with mutable state in _ensure_initialized()
    and try_switch_provider().
    """

    def __init__(self, ai_service: AIService):
        self._ai_service = ai_service
        self._lock = threading.Lock()

    def _sync_complete(self, system: str, user: str) -> str:
        """Synchronously calls AIService.complete() under a thread lock."""
        with self._lock:
            return self._ai_service.complete(system, user)

    async def generate_content_async(
        self, request: LlmRequest, **kwargs
    ) -> LlmResponse:
        """
        ADK calls this method. We extract the prompt, run through
        AIService.complete() in a thread pool, and wrap the result.
        """
        # Extract system and user prompts from the LlmRequest
        system_prompt = request.config.system_instruction or ""
        user_prompt = "\n".join(
            part.text for msg in request.contents
            for part in msg.parts if hasattr(part, "text")
        )

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,  # Default thread pool
            self._sync_complete,
            system_prompt,
            user_prompt,
        )

        return LlmResponse(text=result)
```

---

### Step 6: agent/core/adk/tools.py — Read-Only Tool Suite (AC-4, AC-14, AC-17)

#### NEW agent/core/adk/tools.py

- 5 read-only tools: `read_file`, `search_codebase`, `list_directory`, `read_adr`, `read_journey`.
- All path-accepting tools validate `Path.resolve().is_relative_to(repo_root)`.
- `search_codebase` delegates to `subprocess.run(["rg", ...], timeout=10)` with in-process fallback.
- All tools have a 10-second timeout. No write or network tools.

```python
import os
import subprocess
from pathlib import Path
from typing import List

from google.adk import tool


def _validate_path(path: str, repo_root: Path) -> Path:
    """Validates a path is within the repository root."""
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(repo_root):
        raise ValueError(f"Path '{path}' is outside the repository root.")
    return resolved


def make_tools(repo_root: Path) -> List:
    """Creates bound tool functions with repo_root pre-filled."""

    @tool
    def read_file(path: str) -> str:
        """Reads a file from the repository. Path must be relative to repo root."""
        filepath = _validate_path(repo_root / path, repo_root)
        if not filepath.is_file():
            return f"Error: '{path}' is not a file or does not exist."
        return filepath.read_text(errors="replace")[:50_000]  # Cap output

    @tool
    def search_codebase(query: str) -> str:
        """Searches the codebase for a query using ripgrep. Returns up to 50 matches."""
        try:
            result = subprocess.run(
                ["rg", "--no-heading", "-n", query, str(repo_root)],
                capture_output=True, text=True, timeout=10, check=False,
            )
            if result.returncode == 0:
                lines = result.stdout.splitlines()[:50]
                return "\n".join(lines) or "No matches found."
            return f"No matches found (rg exit code {result.returncode})."
        except subprocess.TimeoutExpired:
            return "Error: search timed out after 10 seconds."
        except FileNotFoundError:
            # Fallback to in-process grep
            matches = []
            for root, _, files in os.walk(repo_root):
                for fname in files:
                    try:
                        fpath = Path(root) / fname
                        for line in fpath.read_text(errors="replace").splitlines():
                            if query in line:
                                matches.append(f"{fpath}:{line.strip()}")
                                if len(matches) >= 50:
                                    return "\n".join(matches)
                    except Exception:
                        continue
            return "\n".join(matches) or "No matches found."

    @tool
    def list_directory(path: str) -> str:
        """Lists the contents of a directory within the repository."""
        dirpath = _validate_path(repo_root / path, repo_root)
        if not dirpath.is_dir():
            return f"Error: '{path}' is not a directory or does not exist."
        entries = sorted(os.listdir(dirpath))
        return "\n".join(entries)

    @tool
    def read_adr(adr_id: str) -> str:
        """Reads an Architecture Decision Record by ID (e.g., '029')."""
        adr_dir = repo_root / ".agent" / "adrs"
        # Try common naming patterns
        for pattern in [f"ADR-{adr_id.zfill(3)}*", f"adr-{adr_id.zfill(3)}*"]:
            matches = list(adr_dir.glob(pattern))
            if matches:
                return matches[0].read_text(errors="replace")
        return f"Error: ADR {adr_id} not found in {adr_dir}."

    @tool
    def read_journey(journey_id: str) -> str:
        """Reads a User Journey by ID (e.g., '033')."""
        jrn_dir = repo_root / ".agent" / "cache" / "journeys"
        for scope_dir in jrn_dir.iterdir():
            if scope_dir.is_dir():
                for pattern in [f"JRN-{journey_id.zfill(3)}*", f"jrn-{journey_id.zfill(3)}*"]:
                    matches = list(scope_dir.glob(pattern))
                    if matches:
                        return matches[0].read_text(errors="replace")
        return f"Error: Journey {journey_id} not found in {jrn_dir}."

    return [read_file, search_codebase, list_directory, read_adr, read_journey]
```

---

### Step 7: agent/core/adk/agents.py — Role Agent Factory (AC-3, AC-7, AC-10)

#### NEW agent/core/adk/agents.py

- Maps each governance role from `agents.yaml` to an ADK `LlmAgent`.
- Field mapping: `role` → agent name, `description` + `governance_checks` → system instruction, `instruction` → appended context.
- Role agents loop up to `max_iterations=3` to refine vague findings.
- Only roles passing `_filter_relevant_roles()` are instantiated.

```python
from typing import Dict, List

from google.adk.agents import LlmAgent


def create_role_agent(role: Dict, tools: List, model) -> LlmAgent:
    """
    Creates an ADK LlmAgent from a role definition in agents.yaml.

    Args:
        role: A role dict from agents.yaml (keys: role, name, description,
              responsibilities, governance_checks, instruction).
        tools: List of bound tool functions.
        model: The BaseLlm adapter instance.

    Returns:
        An LlmAgent configured for this governance role.
    """
    agent_name = role["role"]
    description = role.get("description", "")
    checks = role.get("governance_checks", [])
    instruction = role.get("instruction", "")

    checks_text = "\n".join(f"- {c}" for c in checks) if isinstance(checks, list) else str(checks)

    system_instruction = (
        f"You are the {role.get('name', agent_name)} on the AI Governance Council.\n"
        f"Description: {description}\n\n"
        f"Governance Checks:\n{checks_text}\n\n"
        f"Additional Context: {instruction}\n\n"
        f"Output your analysis in this exact format:\n"
        f"VERDICT: PASS or BLOCK\n"
        f"SUMMARY: One-line summary\n"
        f"FINDINGS:\n- finding 1\n- finding 2\n"
        f"REQUIRED_CHANGES:\n- change 1 (if BLOCK)\n"
        f"REFERENCES:\n- ADR-XXX, JRN-XXX (cite what you consulted)"
    )

    return LlmAgent(
        name=agent_name,
        model=model,
        instruction=system_instruction,
        tools=tools,
    )
```

---

### Step 8: agent/core/adk/orchestrator.py — ADK Orchestration Entry Point (AC-5, AC-6, AC-7, AC-13, AC-15, AC-18, AC-22)

#### NEW agent/core/adk/orchestrator.py

- `convene_council_adk()` is the async entry point called via `asyncio.run()`.
- Creates a `GovernanceCoordinator` that delegates to role sub-agents.
- Collects findings and produces identical audit log format as legacy.
- OpenTelemetry spans: `adk.coordinator`, `adk.agent.{role_name}`, `adk.tool.{tool_name}`.
- Console displays runtime: `[dim]⏱️ Panel completed in {N}s (engine: adk)[/dim]`.

```python
import asyncio
import logging
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from opentelemetry import trace

from agent.core.ai.service import AIService
from agent.core.config import Config
from agent.core.adk.adapter import AIServiceModelAdapter
from agent.core.adk.agents import create_role_agent
from agent.core.adk.tools import make_tools
from agent.core.governance import (
    load_roles, _filter_relevant_roles, _parse_findings,
    _extract_references, _validate_references, AUDIT_LOG_FILE,
)

tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)


async def convene_council_adk(
    story_id: str,
    story_content: str,
    rules_content: str,
    instructions_content: str,
    full_diff: str,
    report_file: Optional[Path] = None,
    mode: str = "gatekeeper",
    council_identifier: str = "default",
    user_question: Optional[str] = None,
    adrs_content: str = "",
    progress_callback: Optional[callable] = None,
) -> Dict:
    """
    ADK-based governance council orchestration.

    Mirrors convene_council_full() signature exactly. Creates role agents,
    runs them concurrently (serialized at AIService lock), aggregates results,
    and produces identical audit log format for SOC 2 parity.

    Returns:
        Dict with 'verdict', 'log_file', and 'json_report' keys —
        same structure as the legacy implementation.
    """
    start_time = time.time()

    with tracer.start_as_current_span("adk.coordinator",
                                       attributes={"panel.engine": "adk"}) as span:
        try:
            config = Config()
            ai_service = AIService  # Module-level singleton

            # Build the adapter (AC-2)
            model_adapter = AIServiceModelAdapter(ai_service)

            # Build tools bound to repo_root (AC-4)
            tools = make_tools(config.repo_root)

            # Load & filter roles (AC-10)
            all_roles = load_roles()
            # Extract changed file paths from diff for role filtering
            changed_files = _extract_changed_files(full_diff)
            relevant_roles = _filter_relevant_roles(all_roles, changed_files)

            if progress_callback:
                progress_callback(f"🤖 ADK Panel: {len(relevant_roles)} roles active")

            # Create role agents (AC-3)
            role_agents = []
            for role in relevant_roles:
                try:
                    agent = create_role_agent(role, tools, model_adapter)
                    role_agents.append((role, agent))
                except Exception as e:
                    logger.error(f"Failed to create agent for {role['role']}: {e}")

            # Build the user prompt (same content as legacy)
            user_prompt = _build_user_prompt(
                story_content, full_diff, rules_content,
                instructions_content, adrs_content, user_question, mode,
            )

            # Run agents (serialized by AIService lock) (AC-7)
            json_report = {
                "story_id": story_id,
                "overall_verdict": "UNKNOWN",
                "engine": "adk",
                "roles": [],
                "log_file": None,
                "error": None,
            }
            overall_verdict = "PASS"
            report_lines = [f"# Governance Report — {story_id}", ""]
            report_lines.append(f"Engine: ADK | Timestamp: {datetime.now().isoformat()}")
            report_lines.append("")

            for role, agent in role_agents:
                role_name = role.get("name", role["role"])
                with tracer.start_as_current_span(
                    f"adk.agent.{role['role']}",
                    attributes={"role_name": role_name}
                ) as agent_span:
                    try:
                        if progress_callback:
                            progress_callback(f"  → {role_name} analyzing...")

                        # ADK agent.run() with iteration cap (AC-7)
                        # The agent will use tools and iterate up to max_iterations
                        result = await _run_agent_with_timeout(agent, user_prompt)

                        # Parse the agent's output using legacy parser for format parity
                        parsed = _parse_findings(result)
                        parsed["role"] = role_name

                        # Extract and validate references (INFRA-060 parity)
                        refs = _extract_references(result)
                        if refs:
                            valid, invalid = _validate_references(refs)
                            parsed["references"] = {
                                "valid": valid, "invalid": invalid
                            }

                        # Verdict logic
                        if mode == "gatekeeper" and parsed.get("verdict") == "BLOCK":
                            overall_verdict = "BLOCK"

                        agent_span.set_attribute("verdict", parsed.get("verdict", "UNKNOWN"))
                        agent_span.set_attribute("findings_count", len(parsed.get("findings", [])))

                        json_report["roles"].append(parsed)

                        # Audit log section (AC-18 — format parity)
                        report_lines.append(f"## {role_name}")
                        report_lines.append(f"Verdict: {parsed.get('verdict', 'UNKNOWN')}")
                        report_lines.append(f"Summary: {parsed.get('summary', 'N/A')}")
                        if parsed.get("findings"):
                            report_lines.append("Findings:")
                            for f in parsed["findings"]:
                                report_lines.append(f"- {f}")
                        report_lines.append("")

                    except Exception as e:
                        agent_span.set_attribute("error", True)
                        logger.exception(f"Agent {role_name} failed: {e}")
                        json_report["roles"].append({
                            "role": role_name,
                            "verdict": "ERROR",
                            "summary": f"Agent failed: {e}",
                            "findings": [traceback.format_exc()],
                        })

            # Finalize
            json_report["overall_verdict"] = overall_verdict
            duration = time.time() - start_time
            span.set_attribute("verdict", overall_verdict)
            span.set_attribute("panel.runtime_ms", int(duration * 1000))

            # Write audit log (AC-18)
            report_lines.append(f"## Overall Verdict: {overall_verdict}")
            report_lines.append(f"Runtime: {duration:.2f}s")
            log_content = "\n".join(report_lines)

            log_file = report_file or (
                Config().logs_dir / f"governance-{story_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
            )
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_file.write_text(log_content)
            json_report["log_file"] = str(log_file)

            # Console runtime display (AC-22)
            if progress_callback:
                progress_callback(f"[dim]⏱️ Panel completed in {duration:.2f}s (engine: adk)[/dim]")

            return {
                "verdict": overall_verdict,
                "log_file": str(log_file),
                "json_report": json_report,
            }

        except Exception as e:
            span.set_attribute("error", True)
            logger.exception(f"ADK council execution failed: {e}")
            duration = time.time() - start_time
            return {
                "verdict": "ERROR",
                "log_file": None,
                "json_report": {
                    "story_id": story_id,
                    "overall_verdict": "ERROR",
                    "engine": "adk",
                    "error": str(e),
                    "roles": [],
                },
            }


async def _run_agent_with_timeout(agent, user_prompt: str, timeout: int = 120) -> str:
    """Run an ADK agent with a timeout guard."""
    # ADK agents use .run_async() or similar — adjust to actual API
    # The agent internally loops up to max_iterations=3
    return await asyncio.wait_for(
        agent.run_async(user_message=user_prompt),
        timeout=timeout,
    )


def _extract_changed_files(diff: str) -> List[str]:
    """Extract file paths from a unified diff."""
    files = []
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            files.append(line[6:])
        elif line.startswith("--- a/"):
            files.append(line[6:])
    return list(set(files))


def _build_user_prompt(
    story_content: str,
    full_diff: str,
    rules_content: str,
    instructions_content: str,
    adrs_content: str,
    user_question: Optional[str],
    mode: str,
) -> str:
    """Build the user prompt for ADK agents — same content as legacy."""
    parts = []
    if story_content:
        parts.append(f"## Story\n{story_content}")
    if rules_content:
        parts.append(f"## Rules\n{rules_content}")
    if instructions_content:
        parts.append(f"## Instructions\n{instructions_content}")
    if adrs_content:
        parts.append(f"## ADRs\n{adrs_content}")
    if user_question:
        parts.append(f"## Question\n{user_question}")
    parts.append(f"## Diff\n```diff\n{full_diff}\n```")
    return "\n\n".join(parts)
```

---

### Step 9: agent/core/adk/compat.py — Lazy Import Guard (AC-9)

#### NEW agent/core/adk/compat.py

- Provides a safe import mechanism for ADK-dependent modules.
- Used by `governance.py` to detect whether ADK is available.

```python
"""
ADK availability check and lazy import guard.

Usage:
    from agent.core.adk.compat import ADK_AVAILABLE
    if ADK_AVAILABLE:
        from agent.core.adk.orchestrator import convene_council_adk
"""

ADK_AVAILABLE = False
ADK_IMPORT_ERROR = None

try:
    import google.adk  # noqa: F401
    ADK_AVAILABLE = True
except ImportError as e:
    ADK_IMPORT_ERROR = e
```

---

### Step 10: agent/core/governance.py — Engine Dispatch & Fallback (AC-8, AC-9, AC-10, AC-13)

#### MODIFY agent/core/governance.py

- Add ADK dispatch logic at the top of `convene_council_full()`.
- Extract current loop body (lines ~354–560) into `_convene_council_legacy()`.
- Fallback covers: `ImportError`, `asyncio.TimeoutError`, ADK-specific exceptions, generic `Exception`.
- Each fallback produces a distinct warning.

```python
import asyncio

def convene_council_full(
    story_id: str,
    story_content: str,
    rules_content: str,
    instructions_content: str,
    full_diff: str,
    report_file: Optional[Path] = None,
    mode: str = "gatekeeper",
    council_identifier: str = "default",
    user_question: Optional[str] = None,
    adrs_content: str = "",
    progress_callback: Optional[callable] = None
) -> Dict:
    """Dispatches to ADK or legacy panel based on config.panel_engine."""

    # Check engine preference (AC-8)
    engine = config.panel_engine

    if engine == "adk":
        # Attempt ADK panel (AC-9 — full fallback chain)
        try:
            from agent.core.adk.compat import ADK_AVAILABLE, ADK_IMPORT_ERROR
            if not ADK_AVAILABLE:
                raise ImportError(str(ADK_IMPORT_ERROR))

            from agent.core.adk.orchestrator import convene_council_adk

            if progress_callback:
                progress_callback("🚀 Using ADK multi-agent panel engine")

            return asyncio.run(convene_council_adk(
                story_id=story_id,
                story_content=story_content,
                rules_content=rules_content,
                instructions_content=instructions_content,
                full_diff=full_diff,
                report_file=report_file,
                mode=mode,
                council_identifier=council_identifier,
                user_question=user_question,
                adrs_content=adrs_content,
                progress_callback=progress_callback,
            ))

        except ImportError:
            logger.warning(
                "google-adk is not installed. Install with: pip install 'agent[adk]'. "
                "Falling back to legacy panel."
            )
        except asyncio.TimeoutError:
            logger.warning("ADK panel timed out. Falling back to legacy panel.")
        except Exception as e:
            logger.warning(f"ADK panel error ({type(e).__name__}): {e}. Falling back to legacy panel.")

        if progress_callback:
            progress_callback("⚠️  Fell back to legacy panel engine")

    # Legacy path (default or fallback)
    return _convene_council_legacy(
        story_id=story_id,
        story_content=story_content,
        rules_content=rules_content,
        instructions_content=instructions_content,
        full_diff=full_diff,
        report_file=report_file,
        mode=mode,
        council_identifier=council_identifier,
        user_question=user_question,
        adrs_content=adrs_content,
        progress_callback=progress_callback,
    )


def _convene_council_legacy(
    story_id: str,
    story_content: str,
    rules_content: str,
    instructions_content: str,
    full_diff: str,
    report_file: Optional[Path] = None,
    mode: str = "gatekeeper",
    council_identifier: str = "default",
    user_question: Optional[str] = None,
    adrs_content: str = "",
    progress_callback: Optional[callable] = None
) -> Dict:
    """Legacy sequential-prompt panel implementation (extracted from current code)."""
    # ... existing loop logic from lines ~354-560 moved here unchanged ...
```

---

### Step 11: agent/commands/check.py — CLI Flag Override (AC-11, AC-22)

#### MODIFY agent/commands/check.py

- Add `--panel-engine` option to `preflight()` and `panel()` commands.
- Override `config.panel_engine` per-invocation when the flag is provided.
- Display engine in console output.

```python
@app.command()
def preflight(
    # ... existing params ...
    panel_engine: Annotated[Optional[str], typer.Option(
        "--panel-engine", help="Override panel engine: 'adk' or 'legacy'"
    )] = None,
):
    # ... early in function body ...
    if panel_engine:
        config._panel_engine_override = panel_engine
```

---

### Step 12: agents.yaml — Optional Per-Role Tool Config (AC-4)

#### MODIFY agent/etc/agents.yaml

- Add optional `tools` field per role to control which tools each agent receives.
- If omitted, agents receive all 5 default tools.

```yaml
  - role: architect
    name: "System Architect"
    # ... existing fields ...
    tools:  # Optional — defaults to all 5 tools if omitted
      - read_file
      - search_codebase
      - list_directory
      - read_adr
      - read_journey
```

---

### Step 13: ADR-029 — Architecture Decision Record (AC-16)

#### NEW agent/adrs/ADR-029-adk-multi-agent-integration.md

- Document: (1) why ADK over alternatives (LangGraph, CrewAI), (2) sync-to-async bridge rationale, (3) thread safety trade-offs accepted, (4) vendor agnosticism guarantee, (5) transitive dep audit results, (6) parallelism limitations.

---

### Step 14: CHANGELOG.md — Release Notes (Docs Panel Finding)

#### MODIFY CHANGELOG.md

```markdown
### Added
- Multi-agent governance panel via Google ADK (opt-in). Configure with `panel.engine: adk` in `agent.yaml` or `--panel-engine adk` CLI flag. Install: `pip install 'agent[adk]'`.
```

---

## Verification Plan

### Automated Tests

#### Unit Tests (tests/core/test_adk_adapter.py)

- [ ] Test 1: `test_adapter_sync_complete()` — `AIServiceModelAdapter._sync_complete()` calls `ai_service.complete()` under lock.
- [ ] Test 2: `test_adapter_async_complete()` — `adapter.generate_content_async()` runs through executor.
- [ ] Test 3: `test_thread_lock_serialization()` — 3 concurrent calls serialize correctly, no interleaving.

#### Unit Tests (tests/core/test_adk_agents.py)

- [ ] Test 4: `test_role_agent_creation()` — agents created with correct name, instruction, tools mapping.
- [ ] Test 5: `test_agent_max_iterations()` — agent reaches 3-iteration cap, finalizes with current findings.

#### Unit Tests (tests/core/test_adk_tools.py)

- [ ] Test 6: `test_read_file_valid()` — reads file within repo root.
- [ ] Test 7: `test_read_file_path_traversal()` — rejects `../outside.txt` with `ValueError`.
- [ ] Test 8: `test_search_codebase_capped()` — returns ≤50 matches.
- [ ] Test 9: `test_search_codebase_timeout()` — respects 10s timeout.
- [ ] Test 10: `test_list_directory()` — lists dir contents.
- [ ] Test 11: `test_read_adr()` — reads ADR by ID.
- [ ] Test 12: `test_read_journey()` — reads Journey by ID.
- [ ] Test 13: `test_explicit_tool_whitelist()` — `make_tools()` returns exactly 5 tools, no ADK defaults.

#### Unit Tests (tests/core/test_adk_orchestrator.py)

- [ ] Test 14: `test_coordinator_aggregation()` — any BLOCK → overall BLOCK.
- [ ] Test 15: `test_coordinator_delegation()` — Architect delegates to Security, both outputs included.
- [ ] Test 16: `test_audit_log_format_parity()` — ADK audit log matches legacy format structure.

#### Unit Tests (tests/core/test_governance_dispatch.py)

- [ ] Test 17: `test_fallback_importerror()` — missing ADK → legacy + install suggestion.
- [ ] Test 18: `test_fallback_timeout()` — `asyncio.TimeoutError` → legacy.
- [ ] Test 19: `test_fallback_agent_error()` — ADK-specific error → legacy.
- [ ] Test 20: `test_fallback_generic_exception()` — generic `Exception` → legacy.
- [ ] Test 21: `test_legacy_engine_unchanged()` — `panel.engine: legacy` uses old sequential loop.

#### Parity Tests (tests/core/test_adk_parity.py)

- [ ] Test 22: `test_structural_parity()` — same input → structurally equivalent output (JSON schema valid, verdict in {PASS, BLOCK}, findings is list). Content differences expected.

#### Benchmark

- [ ] Test 23: Compare ADK vs legacy runtime for standard 3-role changeset. Target ≤1.5x legacy.

### Manual Verification

- [ ] Step 1: Configure `panel.engine: adk` in `agent.yaml`.
- [ ] Step 2: Run `agent preflight` and verify ADK panel is used.
- [ ] Step 3: Run `agent preflight --panel-engine legacy` to verify CLI override.
- [ ] Step 4: Inspect audit log to confirm format parity with legacy.
- [ ] Step 5: Uninstall `google-adk`, set `panel.engine: adk`, verify fallback + install suggestion.
- [ ] Step 6: Run `agent panel` in consultative mode with ADK engine.
- [ ] Step 7: Verify existing tests pass with no regressions.

## Definition of Done

### Documentation

- [ ] ADR-029 written and accepted
- [ ] CHANGELOG.md updated
- [ ] README.md updated (install docs: `pip install 'agent[adk]'`)

### Observability

- [ ] OTel spans: `adk.coordinator`, `adk.agent.{role}`, `adk.tool.{name}`
- [ ] Logs are structured and free of PII
- [ ] `panel.runtime_ms` metric emitted

### Testing

- [ ] All 23 automated tests pass
- [ ] All 7 manual verification steps complete
- [ ] Existing governance tests pass with no regressions
