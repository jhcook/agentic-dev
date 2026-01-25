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

@tool
def draft_new_tool(name: str, code: str) -> str:
    """
    Draft a new custom tool for the voice agent.
    Args:
        name: Name of the tool module (e.g. 'check_weather')
        code: Python code content for the tool
    """
    # Security: Ensure we don't write outside the custom dir
    custom_dir = ".agent/src/backend/voice/tools/custom"
    
    # Sanitize name
    name = os.path.basename(name)
    if not name.isidentifier():
        # simple check, not perfect but helps prevent traversal
        pass 
        
    if not os.path.exists(custom_dir):
        os.makedirs(custom_dir)
        
    filename = f"{name}.py" if not name.endswith(".py") else name
    path = os.path.join(custom_dir, filename)
    
    try:
        with open(path, 'w') as f:
            f.write(code)
        return f"Tool drafted at {path}. Requires review and reload of agent to activate."
    except Exception as e:
        return f"Error creating tool: {e}"

@tool
def list_capabilities() -> str:
    """
    List all available tools and their capabilities.
    """
    tools_dir = ".agent/src/backend/voice/tools"
    files = []
    
    if os.path.exists(tools_dir):
        files = [f for f in os.listdir(tools_dir) if f.endswith(".py") and not f.startswith("__")]
    
    custom_dir = ".agent/src/backend/voice/tools/custom"
    if os.path.exists(custom_dir):
        custom_files = [f for f in os.listdir(custom_dir) if f.endswith(".py") and not f.startswith("__")]
        files += [f"custom/{f}" for f in custom_files]
        
    return f"Available tool modules: {', '.join(files)}"
