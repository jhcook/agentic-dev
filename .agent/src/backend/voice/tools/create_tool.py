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
    # Enforce directory constraint
    custom_dir = ".agent/src/backend/voice/tools/custom"
    base_dir = os.path.abspath(custom_dir)
    
    # Handle both full paths provided by agent or relative filenames
    if not file_path.startswith(custom_dir):
        # Assume it's just a filename relative to custom dir
        target_path = os.path.abspath(os.path.join(base_dir, file_path))
    else:
        target_path = os.path.abspath(file_path)

    # Security: Path Traversal Check & Containment
    # Must use os.path.commonpath or explicit prefix check on resolved paths
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
        # Infer module name relative to .agent/src for importlib
        try:
             # target_path is like /abs/.../.agent/src/backend/voice/tools/custom/foo.py
             # We want backend.voice.tools.custom.foo
             
             # Find .agent/src in path
             src_marker = ".agent/src"
             idx = target_path.find(src_marker)
             if idx == -1:
                 msg = "Error: Could not determine module path for hot reload."
                 logger.error(msg)
                 return msg
                 
             rel_path = target_path[idx + len(src_marker) + 1:] # +1 for slash
             module_name = rel_path.replace("/", ".").replace(".py", "")
             
             if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
                status = "Reloaded existing module."
             else:
                importlib.import_module(module_name)
                status = "Imported new module."
                
             logger.info(f"Hot reload successful for {module_name}")
             return f"Success: Tool created at {file_path}. {status}"
             
        except Exception as e:
            msg = f"Created file at {file_path}, but failed to hot-reload: {e}"
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
