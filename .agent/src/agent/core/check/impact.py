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
Core logic for impact analysis.
"""

import subprocess
from typing import List

from opentelemetry import trace
from agent.core.logger import get_logger
from agent.core.ai.prompts import generate_impact_prompt
from agent.core.ai import ai_service
from agent.core.dependency_analyzer import DependencyAnalyzer
from agent.core.utils import scrub_sensitive_data
from agent.core.check.models import ImpactResult

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

@tracer.start_as_current_span("run_impact_analysis")
def run_impact_analysis(story_id: str, story_content: str, base_branch: str = "main") -> ImpactResult:
    """
    Performs static and AI-driven impact analysis.
    
    Args:
        story_id: The ID of the story being checked.
        story_content: The full content of the story.
        base_branch: The branch to compare against for diffing.
        
    Returns:
        ImpactResult containing analysis details and risk assessment.
    """
    # 1. Identify changes
    try:
        diff = subprocess.check_output(["git", "diff", f"{base_branch}...HEAD"]).decode()
        changed_files = _get_changed_files(base_branch)
    except subprocess.CalledProcessError as e:
        logger.error("Failed to get git diff", extra={"error": str(e), "context": {"base_branch": base_branch}})
        diff = ""
        changed_files = []
    
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
    """Retrieves a list of files changed relative to the base branch."""
    try:
        files = subprocess.check_output(["git", "diff", "--name-only", f"{base}...HEAD"]).decode()
        return [f.strip() for f in files.split("\n") if f.strip()]
    except subprocess.CalledProcessError:
        return []