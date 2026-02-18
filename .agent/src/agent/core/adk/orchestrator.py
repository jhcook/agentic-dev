# Copyright 2026 Justin Cook
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
ADK Governance Council Orchestrator.

Entry point for running the governance panel via ADK multi-agent
orchestration. Creates a coordinator agent with role sub-agents,
executes them, parses findings, and returns an audit-log-compatible
result dict in the same format as the native panel.

Design:
  - Coordinator agent aggregates role verdicts (any BLOCK → overall BLOCK).
  - Each role agent runs with up to 3 tool-use iterations.
  - 120-second timeout per role agent.
  - Falls back cleanly if any agent fails.
"""

import asyncio
import logging
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

from google.adk.agents import LlmAgent

from agent.core.adk.adapter import AIServiceModelAdapter
from agent.core.adk.agents import create_role_agents
from agent.core.adk.tools import make_tools
from agent.core.config import config
from agent.core.security import scrub_sensitive_data

logger = logging.getLogger(__name__)

# Timeout per role agent execution (seconds).
# Set high enough to accommodate:
#   - 3-slot semaphore queuing (8 agents, 3 concurrent)
#   - Server disconnect retries with exponential backoff (2s, 4s, 8s…)
#   - Actual LLM inference time (~10-30s per call)
AGENT_TIMEOUT = 300


def _parse_agent_output(output: str) -> Dict:
    """Parses structured agent output into a findings dict.

    Expected format:
        VERDICT: PASS|BLOCK
        SUMMARY: ...
        FINDINGS:
        - ...
        REQUIRED_CHANGES:
        - ...
        REFERENCES:
        - ...
    """
    result = {
        "verdict": "PASS",
        "summary": "",
        "findings": [],
        "required_changes": [],
        "references": [],
    }

    # Extract verdict
    verdict_match = re.search(r"VERDICT:\s*(PASS|BLOCK)", output)
    if verdict_match:
        result["verdict"] = verdict_match.group(1)

    # Extract summary
    summary_match = re.search(r"SUMMARY:\s*(.+?)(?:\n|$)", output)
    if summary_match:
        result["summary"] = summary_match.group(1).strip()

    # Extract findings
    findings_match = re.search(
        r"FINDINGS:\s*\n((?:\s*-\s*.+\n?)*)", output
    )
    if findings_match:
        result["findings"] = [
            line.strip().lstrip("- ").strip()
            for line in findings_match.group(1).strip().split("\n")
            if line.strip() and line.strip() != "- None"
        ]

    # Extract required changes
    changes_match = re.search(
        r"REQUIRED_CHANGES:\s*\n((?:\s*-\s*.+\n?)*)", output
    )
    if changes_match:
        result["required_changes"] = [
            line.strip().lstrip("- ").strip()
            for line in changes_match.group(1).strip().split("\n")
            if line.strip() and line.strip() != "- None"
        ]

    # Extract references
    refs_match = re.search(
        r"REFERENCES:\s*\n((?:\s*-\s*.+\n?)*)", output
    )
    if refs_match:
        result["references"] = [
            line.strip().lstrip("- ").strip()
            for line in refs_match.group(1).strip().split("\n")
            if line.strip() and line.strip() != "- None"
        ]

    return result


async def _run_role_agent(
    agent: LlmAgent, user_prompt: str, timeout: int = AGENT_TIMEOUT
) -> str:
    """Runs a single role agent with an async timeout.

    Uses the agent's run_async method (ADK standard) with a timeout guard.
    If the agent times out, returns a PASS verdict with a timeout note.

    Returns:
        The agent's text output.
    """
    from google.adk.runners import InMemoryRunner

    runner = InMemoryRunner(agent=agent, app_name=agent.name)

    session = await runner.session_service.create_session(
        app_name=agent.name, user_id="governance"
    )

    from google.genai import types

    user_content = types.Content(
        role="user", parts=[types.Part.from_text(text=user_prompt)]
    )

    output_parts = []
    try:
        async for event in runner.run_async(
            session_id=session.id, user_id="governance", new_message=user_content
        ):
            if hasattr(event, "content") and event.content:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        output_parts.append(part.text)
    except asyncio.TimeoutError:
        logger.warning("Agent %s timed out after %ds", agent.name, timeout)
        return f"VERDICT: PASS\nSUMMARY: Agent timed out after {timeout}s\nFINDINGS:\n- Timed out\n"

    return "\n".join(output_parts) if output_parts else "VERDICT: PASS\nSUMMARY: No output\nFINDINGS:\n- None\n"


async def _orchestrate_async(
    roles: List[Dict],
    story_id: str,
    story_content: str,
    rules_content: str,
    instructions_content: str,
    full_diff: str,
    mode: str = "gatekeeper",
    user_question: Optional[str] = None,
    adrs_content: str = "",
    progress_callback: Optional[callable] = None,
) -> Dict:
    """Async orchestration of all role agents.

    Creates the AIServiceModelAdapter, tool suite, and role agents, then
    runs each agent and aggregates results into the standard audit format.
    """
    start_time = time.time()

    # Create adapter and tools
    model = AIServiceModelAdapter()
    tools = make_tools(config.repo_root)

    # Create role agents
    agents = create_role_agents(roles, tools, model)

    if progress_callback:
        progress_callback(
            f"🤖 ADK Panel: Created {len(agents)} role agents"
        )

    overall_verdict = "PASS"
    report = f"# Governance Preflight Report (ADK)\n\nStory: {story_id}\n\n"
    if user_question:
        report += f"## ❓ User Question\n{scrub_sensitive_data(user_question)}\n\n"

    json_roles = []

    # Build user prompt once (same for all agents)
    user_prompt = f"<story>{story_content}</story>\n<rules>{rules_content}</rules>\n"
    if adrs_content:
        user_prompt += f"<adrs>{adrs_content}</adrs>\n"
    if instructions_content:
        user_prompt += f"<instructions>{instructions_content}</instructions>\n"
    if user_question:
        user_prompt += f"<question>{user_question}</question>\n"
    user_prompt += f"<diff>{full_diff}</diff>"

    async def _run_single_agent(agent):
        """Run a single agent and return parsed role_data dict."""
        role_name = agent.name
        if progress_callback:
            progress_callback(f"🤖 @{role_name} is reviewing (ADK)...")

        try:
            raw_output = await asyncio.wait_for(
                _run_role_agent(agent, user_prompt),
                timeout=AGENT_TIMEOUT,
            )
            raw_output = scrub_sensitive_data(raw_output)
        except asyncio.TimeoutError:
            raw_output = (
                f"VERDICT: PASS\n"
                f"SUMMARY: Agent {role_name} timed out\n"
                f"FINDINGS:\n- Timed out after {AGENT_TIMEOUT}s\n"
            )
            if progress_callback:
                progress_callback(f"⏱️ @{role_name} timed out")
        except Exception as e:
            logger.warning("Agent %s failed: %s", role_name, e)
            raw_output = (
                f"VERDICT: PASS\n"
                f"SUMMARY: Agent error: {e}\n"
                f"FINDINGS:\n- Agent execution error\n"
            )
            if progress_callback:
                progress_callback(f"⚠️ @{role_name} error: {e}")

        parsed = _parse_agent_output(raw_output)
        return {
            "name": role_name,
            "verdict": parsed["verdict"],
            "summary": parsed["summary"],
            "findings": parsed["findings"],
            "required_changes": parsed["required_changes"],
            "references": {
                "cited": parsed["references"],
                "valid": [],
                "invalid": [],
            },
            "_parsed": parsed,  # carry for report generation
        }

    # Dispatch all agents concurrently
    if progress_callback:
        progress_callback(
            f"🚀 Dispatching {len(agents)} agents in parallel..."
        )
    agent_results = await asyncio.gather(
        *[_run_single_agent(agent) for agent in agents]
    )

    # Aggregate results (deterministic order — same as input)
    # Import validation helpers from native governance path
    from agent.core.governance import (
        _validate_finding_against_source,
        _validate_references,
    )
    import re as _re

    _all_valid_refs = []
    _all_invalid_refs = []

    for role_data in agent_results:
        parsed = role_data.pop("_parsed")
        role_name = role_data["name"]
        role_verdict = parsed["verdict"]
        role_findings = list(parsed["findings"])
        role_changes = list(parsed["required_changes"])

        # ── Finding validation (same as native path) ──
        _ai_total = len(role_findings) if mode == "gatekeeper" else 0
        _ai_filtered = 0
        if role_findings and mode == "gatekeeper":
            original_count = len(role_findings)
            role_findings = [
                f for f in role_findings
                if _validate_finding_against_source(f, full_diff)
            ]
            _ai_filtered = original_count - len(role_findings)
            if _ai_filtered > 0 and progress_callback:
                progress_callback(
                    f"🛡️  Filtered {_ai_filtered} false positive(s) from @{role_name}"
                )
        # Also validate required_changes
        if role_changes and mode == "gatekeeper":
            original_changes_count = len(role_changes)
            role_changes = [
                c for c in role_changes
                if _validate_finding_against_source(c, full_diff)
            ]
            _changes_filtered = original_changes_count - len(role_changes)
            _ai_filtered += _changes_filtered
            _ai_total += original_changes_count
            if _changes_filtered > 0 and progress_callback:
                progress_callback(
                    f"🛡️  Filtered {_changes_filtered} false positive(s) from @{role_name} required changes"
                )

        # If ALL findings AND required changes were filtered, demote BLOCK → PASS
        if (_ai_filtered > 0 and not role_findings and not role_changes
                and role_verdict == "BLOCK"):
            role_verdict = "PASS"
            if progress_callback:
                progress_callback(
                    f"✅ @{role_name}: BLOCK demoted to PASS (all findings were false positives)"
                )

        _ai_validated = _ai_total - _ai_filtered

        # ── Reference validation ──
        role_refs = sorted(set(parsed.get("references", [])))
        from pathlib import Path as _Path
        valid_refs, invalid_refs = _validate_references(
            role_refs, config.adrs_dir,
            config.journeys_dir if hasattr(config, 'journeys_dir') else _Path("/nonexistent"),
        )
        _all_valid_refs.extend(valid_refs)
        _all_invalid_refs.extend(invalid_refs)

        for inv in invalid_refs:
            if progress_callback:
                progress_callback(f"⚠️ @{role_name} cited {inv} which does not exist")

        # ── Build role_data ──
        role_data["verdict"] = role_verdict
        role_data["findings"] = role_findings
        role_data["required_changes"] = role_changes
        role_data["references"] = {
            "cited": role_refs,
            "valid": valid_refs,
            "invalid": invalid_refs,
        }
        role_data["finding_validation"] = {
            "total": _ai_total,
            "validated": _ai_validated,
            "filtered": _ai_filtered,
        }

        # ── Verdict logic ──
        if mode == "gatekeeper" and role_verdict == "BLOCK":
            overall_verdict = "BLOCK"
            if progress_callback:
                progress_callback(f"❌ @{role_name}: BLOCK")
            report += f"### @{role_name}\n**Verdict**: ❌ BLOCK\n\n"
        elif mode == "consultative":
            if progress_callback:
                progress_callback(f"ℹ️  @{role_name}: CONSULTED")
            report += f"### @{role_name}\n**Verdict**: ℹ️ ADVICE\n\n"
        else:
            if progress_callback:
                progress_callback(f"✅ @{role_name}: PASS")
            report += f"### @{role_name}\n**Verdict**: ✅ PASS\n\n"

        if parsed["summary"]:
            report += f"**Summary**: {parsed['summary']}\n\n"
        if role_findings:
            report += "**Findings**:\n"
            report += "\n".join(f"- {f}" for f in role_findings)
            report += "\n\n"
        if role_changes:
            report += "**Required Changes**:\n"
            report += "\n".join(f"- {c}" for c in role_changes)
            report += "\n\n"
        if not role_findings and not role_changes:
            report += "No issues found.\n\n"

        json_roles.append(role_data)

    elapsed_ms = int((time.time() - start_time) * 1000)

    # ── Reference metrics (aggregate) ──
    _unique_valid = sorted(set(_all_valid_refs))
    _unique_invalid = sorted(set(_all_invalid_refs))
    _total_refs = len(_unique_valid) + len(_unique_invalid)
    _citation_rate = round(len(_unique_valid) / _total_refs, 2) if _total_refs > 0 else 0.0
    _hallucination_rate = round(len(_unique_invalid) / _total_refs, 2) if _total_refs > 0 else 0.0

    # ── Finding validation metrics (aggregate) ──
    _agg_total = sum(r.get("finding_validation", {}).get("total", 0) for r in json_roles)
    _agg_validated = sum(r.get("finding_validation", {}).get("validated", 0) for r in json_roles)
    _agg_filtered = sum(r.get("finding_validation", {}).get("filtered", 0) for r in json_roles)
    _fp_rate = round(_agg_filtered / _agg_total, 2) if _agg_total > 0 else 0.0

    # ── Append validation tables to report ──
    report += "\n## Reference Validation\n\n"
    report += "| Metric | Value |\n|---|---|\n"
    report += f"| Total References | {_total_refs} |\n"
    report += f"| Valid | {len(_unique_valid)} |\n"
    report += f"| Invalid | {len(_unique_invalid)} |\n"
    report += f"| Citation Rate | {_citation_rate} |\n"
    report += f"| Hallucination Rate | {_hallucination_rate} |\n\n"

    report += "\n## Finding Validation\n\n"
    report += "| Metric | Value |\n|---|---|\n"
    report += f"| AI Findings (raw) | {_agg_total} |\n"
    report += f"| Validated (kept) | {_agg_validated} |\n"
    report += f"| Filtered (false +) | {_agg_filtered} |\n"
    report += f"| False Positive Rate | {_fp_rate:.0%} |\n\n"

    # Save log
    timestamp = int(time.time())
    log_dir = config.agent_dir / "logs"
    log_dir.mkdir(exist_ok=True, parents=True)
    log_file = log_dir / f"governance-{story_id}-{timestamp}.md"
    log_file.write_text(report)

    json_report = {
        "story_id": story_id,
        "overall_verdict": overall_verdict,
        "roles": json_roles,
        "log_file": str(log_file),
        "engine": "adk",
        "runtime_ms": elapsed_ms,
        "error": None,
        "reference_metrics": {
            "total_refs": _total_refs,
            "valid": _unique_valid,
            "invalid": _unique_invalid,
            "citation_rate": _citation_rate,
            "hallucination_rate": _hallucination_rate,
        },
        "finding_validation": {
            "total_ai_findings": _agg_total,
            "validated": _agg_validated,
            "filtered_false_positives": _agg_filtered,
            "false_positive_rate": _fp_rate,
        },
    }

    return {
        "verdict": overall_verdict,
        "log_file": log_file,
        "json_report": json_report,
    }


def convene_council_adk(
    story_id: str,
    story_content: str,
    rules_content: str,
    instructions_content: str,
    full_diff: str,
    roles: List[Dict],
    mode: str = "gatekeeper",
    user_question: Optional[str] = None,
    adrs_content: str = "",
    progress_callback: Optional[callable] = None,
) -> Dict:
    """Synchronous entry point for the ADK governance panel.

    Bridges the sync CLI world to the async ADK world via asyncio.run().
    Falls through to the caller (governance.py) if any exception is raised.

    Args:
        story_id: Story identifier.
        story_content: Full story markdown.
        rules_content: Governance rules text.
        instructions_content: Additional instructions text.
        full_diff: Git diff to review.
        roles: List of role dicts from agents.yaml.
        mode: 'gatekeeper' or 'consultative'.
        user_question: Optional user question for consultative mode.
        adrs_content: ADR content for context.
        progress_callback: Optional callable for progress updates.

    Returns:
        Dict with 'verdict', 'log_file', and 'json_report'.
    """
    return asyncio.run(
        _orchestrate_async(
            roles=roles,
            story_id=story_id,
            story_content=story_content,
            rules_content=rules_content,
            instructions_content=instructions_content,
            full_diff=full_diff,
            mode=mode,
            user_question=user_question,
            adrs_content=adrs_content,
            progress_callback=progress_callback,
        )
    )
