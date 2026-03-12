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
Module for loading documentation-related context.

Provides utilities for summarizing ADRs, mapping test impacts,
and extracting behavioral contracts from tests to feed into the AI context.
"""

import logging
import re as _re

from agent.core.config import config
from agent.core.utils import scrub_sensitive_data

logger = logging.getLogger(__name__)


def load_adrs() -> str:
    """Loads compact summaries of all ADRs from the adrs directory.

    Each ADR is summarized as: Title + State + Decision (first paragraph only).
    This keeps the token budget lean while giving AI full architectural context.
    """
    import re

    context = "ARCHITECTURAL DECISION RECORDS (ADRs):\n"
    context += "ADRs have ULTIMATE PRIORITY over all rules and instructions. "
    context += "When an ADR conflicts with a rule, the ADR WINS. "
    context += "Code that follows an ADR is COMPLIANT and must NOT be flagged as a required change or cause a BLOCK. "
    context += "If a conflict exists, note it as an informational finding only.\n\n"
    has_adrs = False
    adrs_dir = config.agent_dir / "adrs"

    if adrs_dir.exists():
        for adr_file in sorted(adrs_dir.glob("*.md")):
            has_adrs = True
            content = adr_file.read_text(errors="ignore")

            # Extract title (first H1)
            title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else adr_file.stem

            # Extract state
            state_match = re.search(
                r"^##\s+State\s*\n+\s*(\w+)",
                content,
                re.MULTILINE | re.IGNORECASE,
            )
            state = state_match.group(1).strip() if state_match else "UNKNOWN"

            # Extract Decision OR Justification
            # EXC records use "Justification", ADRs use "Decision"
            decision = ""
            # Try Decision first
            decision_match = re.search(
                r"^##\s+Decision\s*\n+(.*?)(?=\n##|\n###|\Z)",
                content,
                re.MULTILINE | re.DOTALL | re.IGNORECASE,
            )
            # Fallback to Justification
            if not decision_match:
                decision_match = re.search(
                    r"^##\s+Justification\s*\n+(.*?)(?=\n##|\n###|\Z)",
                    content,
                    re.MULTILINE | re.DOTALL | re.IGNORECASE,
                )

            if decision_match:
                # Take first paragraph (up to double newline)
                raw = decision_match.group(1).strip()
                first_para = raw.split("\n\n")[0].strip()
                decision = first_para

            # Prefix based on type
            prefix = "[EXCEPTION]" if adr_file.name.startswith("EXC-") else "[ADR]"
            context += f"- **{prefix} {title}** [{state}]: {decision}\n"

    if not has_adrs:
        context += "(No ADRs found)\n"

    return scrub_sensitive_data(context)


def load_test_impact(story_content: str) -> str:
    """
    Find tests that patch modules referenced in the story.
    Builds a test impact matrix identifying all patch targets.
    """
    modules = set()
    for path in _re.findall(r'([a-zA-Z0-9_/.-]+\.py)', story_content):
        dotted = path.replace('/', '.').replace('.py', '')
        if 'agent.' not in dotted:
            dotted = 'agent.' + dotted
        # Clean up leading dots or common prefixes
        dotted = dotted.lstrip('.')
        modules.add(dotted)

    tests_dir = config.agent_dir / "tests"
    if not tests_dir.exists():
        # Try .agent/tests
        tests_dir = config.agent_dir / ".agent" / "tests"
        if not tests_dir.exists():
            return "TEST IMPACT MATRIX:\n(No tests directory found)"

    impact = "TEST IMPACT MATRIX:\n"
    test_count = 0
    patch_pattern = _re.compile(r'patch\(["\']([^"\']+)["\']\)')

    for test_file in sorted(tests_dir.rglob("*.py")):
        try:
            content = test_file.read_text(errors="ignore")
            patches = patch_pattern.findall(content)
            
            relevant_patches = []
            for p in patches:
                if any(m in p for m in modules):
                    relevant_patches.append(p)
            
            if relevant_patches:
                rel_path = test_file.relative_to(config.agent_dir)
                impact += f"{rel_path}:\n"
                for rp in relevant_patches:
                    impact += f"  - patch(\"{rp}\")\n"
                test_count += 1
        except Exception:
            continue

    result = scrub_sensitive_data(impact)
    logger.debug(
        "Test impact count: %d affected files found, %d chars",
        test_count, len(result),
    )
    return result


def load_behavioral_contracts(story_content: str) -> str:
    """
    Extract assertions and default parameter values from related tests.
    Returns behavioral contracts documenting known invariants.
    """
    # Get module stems (e.g. 'service' from 'core/ai/service.py')
    stems = set()
    for path in _re.findall(r'([a-zA-Z0-9_-]+\.py)', story_content):
        stems.add(path.replace('.py', ''))

    tests_dir = config.agent_dir / "tests"
    if not tests_dir.exists():
        tests_dir = config.agent_dir / ".agent" / "tests"
        if not tests_dir.exists():
            return "BEHAVIORAL CONTRACTS:\n"

    contracts = "BEHAVIORAL CONTRACTS:\n"
    
    # Patterns for contracts
    assert_pattern = _re.compile(r'(assert\w*\s*.*?(?:default|fallback|timeout|temperature|auto_)\s*[=!<>]+\s*[^\n,)]+)')
    param_pattern = _re.compile(r'(\w+\([^)]*(?:default|fallback|auto_)\w*\s*=\s*[^,)]+)')

    for test_file in sorted(tests_dir.rglob("*.py")):
        # Only check tests that might be related to the stems
        if not any(stem in test_file.name for stem in stems):
            continue
            
        try:
            content = test_file.read_text(errors="ignore")
            found = []
            found.extend(assert_pattern.findall(content))
            found.extend(param_pattern.findall(content))
            
            if found:
                rel_path = test_file.relative_to(config.agent_dir)
                contracts += f"{rel_path}: {', '.join(found)}\n"
        except Exception:
            continue

    result = scrub_sensitive_data(contracts)
    logger.debug("Behavioral contract count: %d chars extracted", len(result))
    return result
