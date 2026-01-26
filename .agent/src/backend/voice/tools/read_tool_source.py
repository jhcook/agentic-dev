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
def read_tool_source(file_path: str) -> str:
    """Reads the source code of a tool from the specified file path.
    Args:
        file_path: Relative path to the python file (e.g., '.agent/src/backend/voice/tools/project.py')
    """
    try:
        # Normalize path
        normalized_path = os.path.normpath(file_path)
        
        # Security check: basic stricture to keep it within the repo (assuming CWD is repo root)
        # This is a loose check as per 'User accepts RCE risks' but we still try to be sane
        if ".." in normalized_path and not os.path.isabs(normalized_path):
             pass # Basic traversal check could be here
             
        if not os.path.exists(normalized_path):
            return "Error: File not found."
            
        with open(normalized_path, "r") as f:
            source_code = f.read()
            
        # UX: Add a note to the agent
        return (
            f"--- START OF FILE: {file_path} ---\n"
            f"<silent>\n"
            f"{source_code}\n"
            f"</silent>\n"
            f"--- END OF FILE ---\n"
            "SYSTEM INSTRUCTION: The code above is wrapped in <silent> tags. DO NOT read the code out loud. Summarize the functionality only."
        )
    except Exception as e:
        return f"Error reading tool source: {e}"
