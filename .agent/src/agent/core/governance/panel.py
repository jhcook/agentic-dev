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

"""Orchestration loop for the native AI Governance Panel."""

import re
import logging
from typing import Dict, Optional, List
from agent.core.ai import ai_service
from agent.core.governance.roles import load_roles
from agent.core.governance.prompts import get_role_system_prompt
from agent.core.governance.validation import _validate_finding_against_source
from agent.core.governance.syntax_validator import cross_validate_syntax_findings

logger = logging.getLogger(__name__)

def convene_council_full(
    story_id: str,
    story_content: str,
    rules_content: str,
    instructions_content: str,
    full_diff: str,
    thorough: bool = False,
    progress_callback: Optional[callable] = None
) -> Dict:
    """Run the AI Governance Panel review logic."""
    roles = load_roles()
    overall_verdict = "PASS"
    json_roles = []

    for role in roles:
        role_name = role["name"]
        if progress_callback:
            progress_callback(f"🤖 @{role_name} is reviewing...")

        sys_prompt = get_role_system_prompt(role_name, role.get("focus", "General"))
        usr_prompt = f"<story>{story_content}</story><diff>{full_diff}</diff>"
        
        try:
            # temperature=0 for deterministic governance
            raw_review = ai_service.complete(sys_prompt, usr_prompt, temperature=0.0)
            
            # Extract findings from unstructured text (simplified for decomposition example)
            role_findings = re.findall(r"^-\s+(.+)$", raw_review, re.MULTILINE)
            
            # Apply deterministic filters
            role_findings = [f for f in role_findings if _validate_finding_against_source(f, full_diff)]
            
            # Apply Syntax Cross-Validation
            role_findings = cross_validate_syntax_findings(role_findings)
            
            verdict = "BLOCK" if "VERDICT: BLOCK" in raw_review and role_findings else "PASS"
            if verdict == "BLOCK":
                overall_verdict = "BLOCK"

            json_roles.append({
                "name": role_name,
                "verdict": verdict,
                "findings": role_findings
            })
        except Exception as e:
            logger.error("Error in @%s review: %s", role_name, e)

    return {
        "verdict": overall_verdict,
        "json_report": {"roles": json_roles, "overall_verdict": overall_verdict}
    }
