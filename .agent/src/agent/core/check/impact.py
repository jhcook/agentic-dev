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
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from opentelemetry import trace
from agent.core.logger import get_logger
from agent.core.config import config
from agent.core.utils import scrub_sensitive_data
from agent.core.ai.prompts import generate_impact_prompt
from agent.core.check.models import ImpactResult

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

def update_story_impact_summary(story_id: str, analysis: str, found_file: Optional[Path] = None) -> bool:
    """Update the impact summary section of a story file.
    
    Rewrites the markdown file matching the story ID to embed the generated AI 
    or static impact analysis summary block.
    
    Args:
        story_id: The identifier for the story causing the change.
        analysis: The generated impact summary markdown string.
        found_file: The pre-resolved Path to the story file. Uses directory search if None.
        
    Returns:
        True if the file was found and updated successfully, False otherwise.
    """
    if not found_file:
        for file_path in config.stories_dir.rglob(f"{story_id}*.md"):
            if file_path.name.startswith(story_id):
                found_file = file_path
                break
    
    if not found_file:
        return False
        
    story_content = found_file.read_text(errors="ignore")
    if "## Impact Analysis Summary" not in analysis:
        analysis = "## Impact Analysis Summary\n" + analysis
        
    pattern = r"(## Impact Analysis Summary)([\s\S]*?)(?=\n## |$)"
    if re.search(pattern, story_content):
        new_content = re.sub(pattern, analysis.strip(), story_content)
        found_file.write_text(new_content)
    else:
        found_file.write_text(story_content + "\n\n" + analysis)
    return True

def run_impact_analysis(
    story_id: str,
    offline: bool = False,
    base: Optional[str] = None,
    update_story: bool = False,
    provider: Optional[str] = None,
    rebuild_index: bool = False
) -> ImpactResult:
    """
    Performs static and AI-driven impact analysis.
    
    It maps changes between `base` and HEAD onto the project architecture utilizing
    dependency graphs, generates a human-readable risk summary, and optionally 
    calls out to a LLM provider (when `offline=False`) to review the diff 
    in context of the linked story.
    
    Args:
        story_id: The identifier for the story causing the change.
        offline: Disables LLM integration. Requires local inference only.
        base: The base branch for the diff. Defaults to cached index.
        update_story: Overwrites the 'Impact Analysis Summary' section of the markdown.
        provider: AI Provider string.
        rebuild_index: Forces rebuild of the journey DB graph.
        
    Returns:
        ImpactResult containing lists of affected files and risk analysis.
    """
    with tracer.start_as_current_span("run_impact_analysis"):
        result: ImpactResult = {
            "story_id": story_id,
        "impact_summary": "",
        "changed_files": [],
        "reverse_dependencies": {},
        "risk_assessment": "",
        "tokens_used": 0,
        "is_offline": offline,
        "components": set(),
        "total_impacted": 0,
        "affected_journeys": [],
        "test_markers": [],
        "ungoverned_files": [],
        "rebuild_result": None,
        "story_updated": False,
        "story_file_name": None,
        "error": None
    }
    
    # 1. Find the story file
    found_file = None
    for file_path in config.stories_dir.rglob(f"{story_id}*.md"):
        if file_path.name.startswith(story_id):
            found_file = file_path
            break
            
    if not found_file:
         result["error"] = f"Story file not found for {story_id}"
         return result
         
    result["story_file_name"] = found_file.name
    story_content = found_file.read_text(errors="ignore")

    # 2. Get Diff
    if base:
        cmd = ["git", "diff", "--name-only", f"{base}...HEAD"]
        diff_cmd = ["git", "diff", f"{base}...HEAD", "."]
    else:
        cmd = ["git", "diff", "--cached", "--name-only"]
        diff_cmd = ["git", "diff", "--cached", "."]
        
    res = subprocess.run(cmd, capture_output=True, text=True)
    files = res.stdout.strip().splitlines()
    
    if not files or files == ['']:
        return result
        
    result["changed_files"] = files

    # 3. Generate Analysis
    analysis = "Static Impact Analysis:\n" + "\n".join(f"- {f}" for f in files)
    
    if not offline:
        try:
            from agent.core.ai import ai_service
            if provider:
                ai_service.set_provider(provider)
                
            diff_res = subprocess.run(diff_cmd, capture_output=True, text=True)
            full_diff = diff_res.stdout
            
            full_diff_scrubbed = scrub_sensitive_data(full_diff)
            story_content_scrubbed = scrub_sensitive_data(story_content)
            
            prompt = generate_impact_prompt(diff=full_diff_scrubbed, story=story_content_scrubbed)
            logger.debug(
                "AI impact prompt: %d chars, diff: %d chars",
                len(prompt),
                len(full_diff),
            )
            analysis = ai_service.get_completion(prompt)
        except Exception as e:
            result["error"] = f"AI Analysis Failed: {e}"
            # Keep the static analysis so the caller can present it in typer.edit
    else:
        from agent.core.dependency_analyzer import DependencyAnalyzer
        repo_root = Path.cwd()
        analyzer = DependencyAnalyzer(repo_root)
        
        changed_paths = [Path(f) for f in files]
        
        all_files = []
        for pattern in ['**/*.py', '**/*.js', '**/*.ts', '**/*.tsx']:
            all_files.extend(repo_root.glob(pattern))
        all_files = [f.relative_to(repo_root) for f in all_files]
        
        reverse_deps = analyzer.find_reverse_dependencies(changed_paths, all_files)
        total_impacted = sum(len(deps) for deps in reverse_deps.values())
        
        components = set()
        for f in files:
            parts = Path(f).parts
            if len(parts) > 1:
                components.add(parts[0])
            else:
                components.add("root")
                
        result["components"] = components
        result["total_impacted"] = total_impacted
        result["reverse_dependencies"] = {str(k): [str(v) for v in vals] for k, vals in reverse_deps.items()}
        
        analysis = f"""## Impact Analysis Summary\n
**Components**: {', '.join(sorted(components))}
**Files Changed**: {len(files)}
**Reverse Dependencies**: {total_impacted} file(s) impacted

### Changed Files
{chr(10).join('- ' + f for f in files)}

### Risk Summary
- Blast radius: {'🔴 High' if total_impacted > 20 else '🟡 Medium' if total_impacted > 5 else '🟢 Low'} ({total_impacted} dependent files)
- Components affected: {len(components)}
"""
        
    result["impact_summary"] = analysis
    result["risk_assessment"] = analysis

    # 3b. Journey Impact Mapping
    from agent.db.journey_index import get_affected_journeys, is_stale, rebuild_index as rebuild_journey_index
    from agent.db.init import get_db_path
    import sqlite3 as _sqlite3
    
    db_path = get_db_path()
    jconn = _sqlite3.connect(db_path)
    repo_root_path = config.repo_root
    journeys_dir = config.journeys_dir
    
    if rebuild_index or is_stale(jconn, journeys_dir):
        idx_result = rebuild_journey_index(jconn, journeys_dir, repo_root_path)
        result["rebuild_result"] = idx_result
        
    affected = get_affected_journeys(jconn, files, repo_root_path)
    jconn.close()
    
    if affected:
        result["affected_journeys"] = affected
        test_markers: list[str] = []
        governed_files = set()
        for j in affected:
            tests = j.get("tests", [])
            for t in tests:
                test_markers.append(t)
            governed_files.update(j["matched_files"])
            
        result["test_markers"] = test_markers
        result["ungoverned_files"] = [f for f in files if f not in governed_files]
        
    # 4. Update Story
    if update_story and not result["error"]:
        result["story_updated"] = update_story_impact_summary(story_id, analysis, found_file)
        
    return result