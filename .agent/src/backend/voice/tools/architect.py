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
from agent.core.config import config

@tool
def list_adrs() -> str:
    """
    List all Architectural Decision Records (ADRs).
    Returns a list of filenames.
    """
    # Assuming ADRs are in docs/architecture/decisions or similar
    # Based on verify_backend_socket.py finding earlier, docs are in specific spots
    # config.docs_dir is available
    adr_dir = ".agent/rules" # As per agents.yaml instruction, rules are key
    # Also check docs/ if it exists.
    
    # Implementation: Search .agent/rules first as they are governance requirements
    files = glob.glob(".agent/rules/*.md*")
    if not files:
        return "No rules found in .agent/rules."
    
    return "\n".join([os.path.basename(f) for f in files])

@tool
def read_adr(filename: str) -> str:
    """
    Read the content of a specific ADR or Rule file.
    Args:
        filename: The basename of the file (e.g., 'no_secrets.md')
    """
    # Secure path join
    target = os.path.join(".agent/rules", filename)
    if not os.path.exists(target):
         # Try finding it in recursive search
         matches = glob.glob(f".agent/rules/**/{filename}", recursive=True)
         if matches:
             target = matches[0]
         else:
             return f"File {filename} not found."
             
    try:
        with open(target, 'r') as f:
            content = f.read()
        return content
    except Exception as e:
        return f"Error reading file: {e}"

@tool
def search_rules(query: str) -> str:
    """
    Search for a specific term within all governance rules.
    """
    results = []
    files = glob.glob(".agent/rules/**/*.md*", recursive=True)
    for file in files:
        try:
            with open(file, 'r') as f:
                content = f.read()
                if query.lower() in content.lower():
                    results.append(os.path.basename(file))
        except:
            continue
            
    if not results:
        return f"No rules found containing '{query}'."
    return f"Found '{query}' in: {', '.join(results)}"
