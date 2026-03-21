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

"""Runbook helper functions.

Extracted from ``runbook.py`` (INFRA-165) to keep module LOC under the
1000-line quality gate.  Contains complexity scoring, decomposition plan
generation, journey context loading, dynamic rule retrieval, and split
request parsing.
"""

import json
import re
import time
from dataclasses import dataclass
from typing import List, Optional

from opentelemetry import trace
from rich.console import Console

from agent.core.config import config
from agent.core.logger import get_logger

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)
console = Console()


@dataclass
class ComplexityMetrics:
    """Heuristic complexity metrics for a story."""

    step_count: int
    context_width: int
    verb_intensity: float
    estimated_loc: float
    file_count: int


def score_story_complexity(content: str) -> ComplexityMetrics:
    """Calculate heuristic complexity score from story content.

    Scoring is regex-based and runs in <100ms (no AI call).

    Args:
        content: Raw story markdown content.

    Returns:
        ComplexityMetrics with step_count, context_width, verb_intensity,
        estimated_loc, and file_count.
    """
    with tracer.start_as_current_span("forecast.score_complexity") as span:
        step_count = len(re.findall(r"^\s*-\s*\[ \]", content, re.MULTILINE))
        context_width = len(re.findall(r"ADR-\d+|JRN-\d+", content))

        verb_intensity = 1.0
        if re.search(r"\bmigrate\b", content, re.IGNORECASE):
            verb_intensity = 2.0
        elif re.search(r"\brefactor\b", content, re.IGNORECASE):
            verb_intensity = 1.5

        file_count = len(re.findall(r"####\s*\[(?:MODIFY|NEW|DELETE|ADD)\]", content))
        estimated_loc = (step_count * 40) * verb_intensity

        span.set_attribute("forecast.step_count", step_count)
        span.set_attribute("forecast.context_width", context_width)
        span.set_attribute("forecast.verb_intensity", verb_intensity)
        span.set_attribute("forecast.estimated_loc", estimated_loc)
        span.set_attribute("forecast.file_count", file_count)

        logger.info(
            "forecast step_count=%d context_width=%d verb_intensity=%.1f "
            "estimated_loc=%.0f file_count=%d",
            step_count, context_width, verb_intensity, estimated_loc, file_count,
        )

        return ComplexityMetrics(
            step_count=step_count,
            context_width=context_width,
            verb_intensity=verb_intensity,
            estimated_loc=estimated_loc,
            file_count=file_count,
        )


def generate_decomposition_plan(story_id: str, story_content: str) -> str:
    """Generate a decomposition plan for an over-budget story using AI.

    Args:
        story_id: The story identifier (e.g. INFRA-093).
        story_content: Raw story markdown content.

    Returns:
        Path to the generated plan file.
    """
    from agent.core.ai import ai_service  # ADR-025: lazy init

    scope_match = re.match(r"([A-Z]+)-\d+", story_id)
    scope = scope_match.group(1) if scope_match else "MISC"
    plan_dir = config.plans_dir / scope
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plan_dir / f"{story_id}-plan.md"

    system_prompt = (
        "You are a story decomposer. Given a story that exceeds complexity "
        "limits, produce a Plan with child stories. Each child must be "
        "scoped to ≤400 LOC. Output markdown with child story references. "
        "IMPORTANT: In every Impact Analysis section, ALL file paths MUST be "
        "exact repository-relative paths (e.g. .agent/src/agent/commands/runbook.py). "
        "Do NOT use generic component names like 'Orchestrator' or bare filenames "
        "like 'parser.py'."
    )
    user_prompt = f"Decompose this story:\n\n{story_content}"

    plan_content = ai_service.complete(system_prompt, user_prompt)
    if plan_content:
        plan_path.write_text(plan_content)
    else:
        plan_path.write_text(f"# Plan: {story_id}\n\nAI returned empty plan.")

    return str(plan_path)


def load_journey_context() -> str:
    """Load existing journey YAML files for context injection.

    Returns a size-bounded, scrubbed string of journey content.
    """
    from agent.core.utils import scrub_sensitive_data

    journeys_content = ""
    if config.journeys_dir.exists():
        for jf in config.journeys_dir.rglob("*.yaml"):
            journeys_content += f"\n---\n{jf.read_text()}"

    if journeys_content:
        return scrub_sensitive_data(journeys_content[:5000])
    return "None defined yet."


def retrieve_dynamic_rules(story_content: str, targeted_context: str) -> str:
    """Perform semantic retrieval of contextual rules based on story impact (INFRA-135).

    Classifies .agent/rules/ into core (always included) and contextual
    (retrieved via RAG). Reduces token count by ≥50%.

    Args:
        story_content: The user story markdown.
        targeted_context: Introspection of touched files.

    Returns:
        Assembled string of relevant governance rules.
    """
    start_time = time.monotonic()
    rules_dir = config.rules_dir

    # AC-1: Audit and Classify
    # Core: Identity, Governance, Security, QA, Architect (Foundation)
    CORE_PREFIXES = ("000", "001", "002", "003", "004")

    core_content = []
    contextual_candidates = []

    if rules_dir.exists():
        for rule_file in sorted(rules_dir.glob("*.mdc")):
            if rule_file.name.startswith(CORE_PREFIXES):
                core_content.append(f"--- CORE RULE: {rule_file.name} ---\n{rule_file.read_text()}")
            else:
                contextual_candidates.append(rule_file.name)

    # AC-3: Retrieval Step
    query = f"{story_content}\n\nTOUCHED FILES:\n{targeted_context}"
    retrieved_content = ""
    source = "NONE"
    fallback_used = False

    try:
        # Try local Vector DB first as it's the primary fallback for Rule Diet
        from agent.db.journey_index import JourneyIndex
        console.print("[dim]ℹ️  Populating shards in vector index...[/dim]")
        idx = JourneyIndex()
        # Search for contextual rules specifically
        retrieved_content = idx.search(f"Governance rules for: {query}", k=4)
        source = "ChromaDB"
        fallback_used = True
    except Exception as e:
        logger.warning(f"Rule retrieval failed: {e}")
        source = "FAILED"

    # AC-4: Fallback Mechanism
    # If retrieval failed or returned empty, we still have core_content (Security + QA)

    latency = (time.monotonic() - start_time) * 1000

    # NFR: SOC2/Observability logging
    logger.info("rule_retrieval", extra={
        "source": source,
        "count": 4 if retrieved_content else 0,
        "latency_ms": latency,
        "fallback_used": fallback_used
    })

    combined = "\n\n".join(core_content)
    if retrieved_content:
        combined += "\n\n### CONTEXTUAL RULES (RETRIEVED) ###\n\n" + retrieved_content

    return combined


def parse_split_request(content: str) -> Optional[dict]:
    """Extract and parse SPLIT_REQUEST JSON from AI response.

    Handles:
    - Pure JSON response
    - JSON embedded in markdown code fences
    - Malformed JSON (returns None -> treat as normal runbook)

    Args:
        content: Raw AI response string.

    Returns:
        Parsed dict if valid SPLIT_REQUEST, None otherwise.
    """
    # Try direct parse first
    try:
        data = json.loads(content.strip())
        if isinstance(data, dict) and data.get("SPLIT_REQUEST"):
            return data
    except (json.JSONDecodeError, ValueError):
        pass

    # Try extracting from markdown code fences (\n made optional for AI variance)
    json_match = re.search(r"```(?:json)?\s*\n?(.+?)\n?\s*```", content, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1).strip())
            if isinstance(data, dict) and data.get("SPLIT_REQUEST"):
                return data
        except (json.JSONDecodeError, ValueError):
            pass

    # Malformed or not a SPLIT_REQUEST -- graceful fallback
    logger.debug(
        "SPLIT_REQUEST marker found but JSON parse failed, treating as normal runbook"
    )
    return None
