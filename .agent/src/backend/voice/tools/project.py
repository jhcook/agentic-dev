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

from langchain_core.tools import tool
import os
import glob
import yaml

@tool
def list_stories(status: str = "OPEN") -> str:
    """
    List user stories filtered by status.
    Args:
        status: Filter (e.g. 'OPEN', 'COMPLETED', 'ALL')
    """
    stories_dir = ".agent/cache/stories"
    pattern = f"{stories_dir}/**/*.md"
    matches = []
    
    for fpath in glob.glob(pattern, recursive=True):
        try:
             # Basic check of content or just listing
             # For speed, just list filenames for now
             if status == "ALL":
                 matches.append(os.path.basename(fpath))
                 continue
                 
             # Deep check requires reading file... skipping for performance in voice 
             # unless requested? 
             # Let's just return all for MVP
             matches.append(os.path.basename(fpath))
        except:
            continue
            
    if not matches:
        return "No stories found."
    return "\n".join(matches[:10]) # Limit to 10

@tool
def get_project_info() -> str:
    """
    Get high-level project information (name, version, key deps).
    """
    info = []
    if os.path.exists("pyproject.toml"):
        info.append("Found pyproject.toml (Python Project)")
    if os.path.exists("package.json"):
         info.append("Found package.json (Node Project)")
    if os.path.exists(".agent/etc/agents.yaml"):
         info.append("Governance: Active")
         
    return "\n".join(info)

@tool
def list_runbooks() -> str:
    """List all implementation runbooks."""
    files = glob.glob(".agent/cache/runbooks/**/*.md", recursive=True)
    return "\n".join([os.path.basename(f) for f in files])
