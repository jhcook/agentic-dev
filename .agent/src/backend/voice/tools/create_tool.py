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
import logging
from agent.tools import dynamic

logger = logging.getLogger(__name__)

@tool
def create_tool(file_path: str, code: str) -> str:
    """
    Creates a new tool (Python file) in the core 'custom' tools directory and hot-reloads it.
    
    Args:
        file_path: Relative path to the file. MUST be inside '.agent/src/agent/tools/custom/'.
                   Example: 'my_new_tool.py' or 'integrations/slack_tool.py'
        code: The valid Python code for the tool.
    """
    try:
        # Delegate to core dynamic engine
        return dynamic.create_tool(file_path, code)
    except dynamic.PathTraversalError as e:
        return f"Error: {e}"
    except dynamic.SecurityError as e:
        return str(e)
    except SyntaxError as e:
        return f"Error: Invalid Python syntax in code: {e}"
    except Exception as e:
        return f"Error creating tool: {e}"
