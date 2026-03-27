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
Project domain tools for story and runbook management.
"""

import logging
from pathlib import Path
from typing import List, Optional
from agent.utils.tool_security import validate_safe_path

logger = logging.getLogger(__name__)

def list_stories(repo_root: Path, **kwargs) -> str:
    """
    Lists all available stories in the repository cache.
    """
    stories_dir = repo_root / ".agent" / "cache" / "stories"
    if not stories_dir.exists():
        return "Stories directory not found."
    files = list(stories_dir.glob("*.md"))
    if not files:
        return "No stories found."
    return "\n".join([f.stem for f in sorted(files)])

def read_story(story_id: str, repo_root: Path, **kwargs) -> str:
    """
    Reads the content of a specific story by ID.
    """
    path = repo_root / ".agent" / "cache" / "stories" / f"{story_id}.md"
    try:
        safe_path = validate_safe_path(path, repo_root)
        if not safe_path.exists():
            return f"Error: Story '{story_id}' not found."
        return safe_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading story: {str(e)}"

def read_runbook(story_id: str, repo_root: Path, **kwargs) -> str:
    """
    Reads the runbook associated with a specific story ID.
    """
    path = repo_root / ".agent" / "cache" / "runbooks" / f"{story_id}-runbook.md"
    try:
        safe_path = validate_safe_path(path, repo_root)
        if not safe_path.exists():
            return f"Error: Runbook for story '{story_id}' not found."
        return safe_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading runbook: {str(e)}"

def match_story(query: str, repo_root: Path, **kwargs) -> str:
    """
    Matches a natural language query against available story titles and content.
    """
    stories_dir = repo_root / ".agent" / "cache" / "stories"
    if not stories_dir.exists():
        return "No stories directory found to match against."
    
    matches = []
    query_lower = query.lower()
    for f in stories_dir.glob("*.md"):
        if query_lower in f.name.lower():
            matches.append(f.stem)
            continue
        try:
            if query_lower in f.read_text(encoding="utf-8").lower():
                matches.append(f.stem)
        except Exception:
            continue
            
    if not matches:
        return f"No stories matching '{query}' were found."
    return "Matching stories: " + ", ".join(matches[:10])

def list_workflows(repo_root: Path, **kwargs) -> str:
    """
    Lists available automated workflows.
    """
    wf_dir = repo_root / ".agent" / "workflows"
    if not wf_dir.exists():
        return "Workflows directory not found."
    files = list(wf_dir.glob("*.yaml")) + list(wf_dir.glob("*.yml"))
    if not files:
        return "No workflows found."
    return "\n".join([f.name for f in sorted(files)])

def fix_story(story_id: str, update: str, repo_root: Path, **kwargs) -> str:
    """
    Applies an update block to a story document.
    """
    path = repo_root / ".agent" / "cache" / "stories" / f"{story_id}.md"
    try:
        safe_path = validate_safe_path(path, repo_root)
        if not safe_path.exists():
            return f"Error: Story '{story_id}' not found."
        
        with open(safe_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n## Correction/Update\n\n{update}\n")
        return f"Successfully applied update to {story_id}."
    except Exception as e:
        return f"Error fixing story: {str(e)}"

def list_capabilities(**kwargs) -> str:
    """
    Lists all registered tools and their descriptions.
    """
    registry = kwargs.get("registry")
    if not registry:
        return "Error: ToolRegistry context unavailable."
    
    tools = registry.list_tools()
    lines = ["Available Capabilities:"]
    for tool in sorted(tools, key=lambda x: x.name):
        lines.append(f"- {tool.name}: {tool.description}")
    return "\n".join(lines)
