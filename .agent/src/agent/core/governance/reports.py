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

"""Report formatting and assembly for governance reviews."""

import json
import time
from pathlib import Path
from typing import Dict, List
from agent.core.config import config

def assemble_json_report(story_id: str, roles_data: List[Dict], verdict: str) -> Dict:
    """Assemble final structured JSON preflight report."""
    report = {
        "story_id": story_id,
        "overall_verdict": verdict,
        "timestamp": int(time.time()),
        "roles": roles_data,
        "finding_validation": {
            "total": sum(r.get("finding_validation", {}).get("total", 0) for r in roles_data),
            "validated": sum(r.get("finding_validation", {}).get("validated", 0) for r in roles_data),
            "filtered": sum(r.get("finding_validation", {}).get("filtered", 0) for r in roles_data),
        }
    }
    return report

def save_markdown_report(story_id: str, content: str) -> Path:
    """Persist the human-readable Markdown report to logs."""
    log_dir = config.agent_dir / "logs"
    log_dir.mkdir(exist_ok=True, parents=True)
    log_file = log_dir / f"governance-{story_id}-{int(time.time())}.md"
    log_file.write_text(content)
    return log_file
