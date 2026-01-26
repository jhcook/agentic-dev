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
import inspect

@tool
def list_capabilities() -> str:
    """
    List all available tools and their detailed functional descriptions.
    Use this to understand what you can do.
    """
    # Import here to avoid circular dependencies
    from backend.voice.tools.registry import get_all_tools
    
    tools = get_all_tools()
    descriptions = []
    
    for t in tools:
        name = t.name
        # Get docstring, clean it up
        doc = inspect.getdoc(t.func) if hasattr(t, 'func') else t.description
        if not doc:
            doc = "No description available."
        
        # Format for readability
        descriptions.append(f"- **{name}**: {doc}")
        
    return "\n\n".join(descriptions)
