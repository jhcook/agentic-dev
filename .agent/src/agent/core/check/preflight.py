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
Preflight governance orchestration.
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

from agent.core.config import config
from agent.core.logger import get_logger
from agent.core.utils import scrub_sensitive_data
from opentelemetry import trace
from agent.core.governance import convene_council_full
from agent.core.check.models import PreflightResult
from agent.core.check.system import validate_linked_journeys
from agent.core.check.quality import check_journey_coverage
from agent.core.check.impact import run_impact_analysis

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

@tracer.start_as_current_span("execute_preflight")
def execute_preflight(story_id: str, story_content: str) -> PreflightResult:
    """
    Orchestrates the full preflight check sequence.
    
    Args:
        story_id: The ID of the story being checked.
        story_content: The full content of the story.
        
    Returns:
        PreflightResult containing verdicts and metrics.
    """
    # 1. System & Quality Checks
    sys_val = validate_linked_journeys(story_id)
    quality = check_journey_coverage(story_id)
    
    # 2. Impact Analysis
    impact = run_impact_analysis(story_id, story_content)
    
    # 3. Governance Council
    previous_verdicts = _load_previous_verdicts()
    verdicts = convene_council_full(
        story_content=scrub_sensitive_data(story_content),
        diff=scrub_sensitive_data(_get_current_diff()),
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
    """Loads previous verdicts from the .preflight_result file if it exists."""
    path = config.cache_dir / ".preflight_result"
    if path.exists():
        try:
            return path.read_text()
        except Exception as e:
            logger.warning("Failed to read .preflight_result", extra={"error": str(e)})
    return ""

def _persist_result(result: PreflightResult) -> None:
    """Persists the preflight result to a local file."""
    try:
        (config.cache_dir / ".preflight_result").write_text(json.dumps(result, indent=2))
    except Exception as e:
        logger.error("Failed to persist .preflight_result", extra={"error": str(e)})

def _get_current_diff() -> str:
    """Retrieves the current git diff of the workspace."""
    try:
        result = subprocess.run(["git", "diff", "HEAD"], capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError:
        return ""