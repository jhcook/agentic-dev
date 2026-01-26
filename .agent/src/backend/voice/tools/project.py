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
             filename = os.path.basename(fpath)
             if status == "ALL":
                 matches.append(filename)
                 continue
                 
             # Check content for status
             with open(fpath, 'r') as f:
                 content = f.read()
                 # Simple check for "Status: <status>" or "State: <status>"
                 # Case insensitive check
                 if f"State: {status}" in content or f"Status: {status}" in content or \
                    f"State:\n{status}" in content or f"Status:\n{status}" in content:
                     matches.append(filename)
        except:
            continue
            
    if not matches:
        return f"No stories found with status '{status}'."
    return "\n".join(matches[:20]) # Limit to 20

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
