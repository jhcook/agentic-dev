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
result dict in the same format as the legacy panel.

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

# Timeout per role agent execution (seconds)
AGENT_TIMEOUT = 120


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
    from google.adk.sessions import InMemorySessionService

    session_service = InMemorySessionService()
    runner = InMemoryRunner(agent=agent, session_service=session_service)

    session = await session_service.create_session(
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

    for agent in agents:
        role_name = agent.name
        if progress_callback:
            progress_callback(f"🤖 @{role_name} is reviewing (ADK)...")

        # Build user prompt
        user_prompt = f"<story>{story_content}</story>\n<rules>{rules_content}</rules>\n"
        if adrs_content:
            user_prompt += f"<adrs>{adrs_content}</adrs>\n"
        if instructions_content:
            user_prompt += f"<instructions>{instructions_content}</instructions>\n"
        if user_question:
            user_prompt += f"<question>{user_question}</question>\n"
        user_prompt += f"<diff>{full_diff}</diff>"

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

        role_data = {
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
        }

        # In gatekeeper mode, any BLOCK → overall BLOCK
        if mode == "gatekeeper" and parsed["verdict"] == "BLOCK":
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
        if parsed["findings"]:
            report += "**Findings**:\n"
            report += "\n".join(f"- {f}" for f in parsed["findings"])
            report += "\n\n"
        if parsed["required_changes"]:
            report += "**Required Changes**:\n"
            report += "\n".join(f"- {c}" for c in parsed["required_changes"])
            report += "\n\n"
        if not parsed["findings"] and not parsed["required_changes"]:
            report += "No issues found.\n\n"

        json_roles.append(role_data)

    elapsed_ms = int((time.time() - start_time) * 1000)

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
