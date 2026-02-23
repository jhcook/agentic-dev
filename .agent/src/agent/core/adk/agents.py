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
Role → ADK Agent factory.

Maps governance role definitions from agents.yaml into ADK LlmAgent
instances. Each agent receives a tailored system instruction built from
the role's description, governance checks, and output format requirements.
"""

import logging
from typing import Dict, List

from google.adk.agents import LlmAgent

logger = logging.getLogger(__name__)

# Maximum iterations an agent may execute before finalizing output.
MAX_ITERATIONS = 3


def create_role_agent(role: Dict, tools: List, model, other_domains: str = "") -> LlmAgent:
    """Creates an ADK LlmAgent from a role definition in agents.yaml.

    Args:
        role: A role dict from agents.yaml (keys: role, name, description,
              responsibilities, governance_checks, instruction).
        tools: List of bound tool functions.
        model: The BaseLlm adapter instance.
        other_domains: Comma-separated list of other domains to ignore.

    Returns:
        An LlmAgent configured for this governance role.
    """
    agent_name = role["role"]
    description = role.get("description", "")
    checks = role.get("governance_checks", [])
    instruction = role.get("instruction", "")

    checks_text = (
        "\n".join(f"- {c}" for c in checks)
        if isinstance(checks, list)
        else str(checks)
    )

    domain_restriction = f"You are strictly forbidden from evaluating these other domains: {other_domains}.\n" if other_domains else ""

    system_instruction = (
        f"You are the {role.get('name', agent_name)} on the AI Governance Council.\n"
        f"Description: {description}\n\n"
        f"Governance Checks:\n{checks_text}\n\n"
        f"Additional Context: {instruction}\n\n"
        f"{domain_restriction}"
        f"You have access to tools for reading files, searching code, reading ADRs, "
        f"and reading user journeys. Use these tools to validate your findings against "
        f"the actual codebase before issuing a verdict.\n\n"
        f"Output your analysis in this EXACT format:\n"
        f"VERDICT: PASS or BLOCK\n"
        f"SUMMARY: One-line summary\n"
        f"FINDINGS:\n- finding 1 (Source: [Exact file path or ADR ID])\n- finding 2 (Source: [Exact file path or ADR ID])\n"
        f"REQUIRED_CHANGES:\n- change 1 (Source: [Exact file path or ADR ID]) (if BLOCK)\n"
        f"REFERENCES:\n- ADR-XXX, JRN-XXX (cite what you consulted)"
    )

    return LlmAgent(
        name=agent_name,
        model=model,
        instruction=system_instruction,
        tools=tools,
    )


def create_role_agents(
    roles: List[Dict], tools: List, model
) -> List[LlmAgent]:
    """Creates ADK agents for all governance roles.

    Args:
        roles: List of role dicts from agents.yaml.
        tools: List of bound tool functions.
        model: The BaseLlm adapter instance.

    Returns:
        List of configured LlmAgent instances.
    """
    agents = []
    for role in roles:
        try:
            agent_title = role.get("name", role.get("role", "unknown"))
            other_domains = ", ".join(
                [r.get("name", r.get("role", "")) for r in roles if r.get("name", r.get("role", "")) != agent_title]
            )
            agent = create_role_agent(role, tools, model, other_domains)
            agents.append(agent)
            logger.debug("Created ADK agent for role: %s", role.get("name"))
        except Exception as e:
            logger.warning(
                "Failed to create agent for role %s: %s",
                role.get("name", "unknown"),
                e,
            )
    return agents
