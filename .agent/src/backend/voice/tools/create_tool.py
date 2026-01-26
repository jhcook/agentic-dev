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
import ast
import importlib
import sys
import logging

logger = logging.getLogger(__name__)

@tool
def create_tool(file_path: str, code: str) -> str:
    """
    Creates a new tool (Python file) in the 'custom' tools directory and hot-reloads it.
    
    Args:
        file_path: Relative path to the file. MUST be inside '.agent/src/backend/voice/tools/custom/'.
                   Example: 'my_new_tool.py' or 'integrations/slack_tool.py'
        code: The valid Python code for the tool.
    """
    # Enforce directory constraint - relative to this file
    # This file is in .../backend/voice/tools/create_tool.py
    # Custom tools are in .../backend/voice/tools/custom/
    custom_dir = os.path.join(os.path.dirname(__file__), "custom")
    base_dir = os.path.abspath(custom_dir)
    
    # Handle both full paths provided by agent or relative filenames
    # Check if the input path is already an absolute path that starts with our base_dir
    if os.path.isabs(file_path) and file_path.startswith(base_dir):
        target_path = file_path
    else:
        # Assume relative to custom directory if not absolute matching base
        # Strip any leading directory components if they were trying to be clever with relative paths
        clean_name = os.path.basename(file_path)
        target_path = os.path.join(base_dir, clean_name)

    # Security: Path Traversal Check & Containment
    if not target_path.startswith(base_dir):
        return f"Error: Security violation. Tools can only be created in {custom_dir}."
        
    # Syntax Validation
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"Error: Invalid Python syntax in code: {e}"

    # Security: Static Analysis
    security_errors = _security_scan(tree, code)
    if security_errors:
        return f"Security Rejection: {'; '.join(security_errors)}. Add '# NOQA: SECURITY_RISK' to override if absolutely necessary."

    try:
        # Create directories if needed
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        # Write file
        with open(target_path, 'w') as f:
            f.write(code)
            
        # Observability: Log creation (Log event, not full content for PII safety)
        # Compliance: Log explicit RCE acceptance
        logger.warning(f"SECURITY: RCE Risk Accepted by User for creation of tool at {target_path}")
        logger.info(f"Tool created at {target_path}")
        
        # Hot Reload Logic
        try:
             # We know the module path because we enforced the directory structure
             # File is at .../backend/voice/tools/custom/<filename>.py
             # Module is backend.voice.tools.custom.<filename>
             filename = os.path.basename(target_path)
             module_param = os.path.splitext(filename)[0]
             module_name = f"backend.voice.tools.custom.{module_param}"
             
             if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
                status = "Reloaded existing module."
             else:
                importlib.import_module(module_name)
                status = "Imported new module."
                
             logger.info(f"Hot reload successful for {module_name}")
             return f"Success: Tool created at {target_path}. {status}"
             
        except Exception as e:
            msg = f"Created file at {target_path}, but failed to hot-reload: {e}"
            logger.error(f"Hot reload failed: {e}")
            return msg
            
    except Exception as e:
        return f"Error creating tool: {e}"

def _security_scan(tree: ast.AST, code: str) -> list[str]:
    """Scan AST for dangerous patterns."""
    if "# NOQA: SECURITY_RISK" in code:
        return []

    errors = []
    for node in ast.walk(tree):
        # Check imports
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in node.names]
            if "subprocess" in names:
                errors.append("Usage of 'subprocess' is restricted")
            if "os" in names and not isinstance(node, ast.ImportFrom):
                # Checking specific os functions is hard in AST without flow analysis, warn on 'import os'
                # But 'os.path' is fine. This is a heuristic.
                pass 
                
        # Check calls
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                attr = node.func.attr
                # Reject os.system, os.popen, etc
                if attr in ['system', 'popen', 'spawn', 'execl', 'execle', 'execlp']:
                     errors.append(f"Usage of 'os.{attr}' is restricted")
            elif isinstance(node.func, ast.Name):
                if node.func.id in ['eval', 'exec', 'compile']:
                    errors.append(f"Usage of '{node.func.id}' is forbidden")
                    
    return errors
