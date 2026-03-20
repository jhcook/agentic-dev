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

"""Core engine for dynamic tool creation, security scanning, and hot-reloading."""

import ast
import importlib
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Base class for security-related errors in the dynamic tool engine."""
    pass


class PathTraversalError(SecurityError):
    """Raised when a path traversal attempt is detected."""
    pass


def _get_custom_tools_dir() -> Path:
    """
    Returns the absolute path to the custom tools directory.
    
    Returns:
        Path: The absolute path to .agent/src/agent/tools/custom/
    """
    # This file is at .agent/src/agent/tools/dynamic.py
    current_file = Path(os.path.abspath(__file__))
    return current_file.parent / "custom"


def _security_scan(tree: ast.AST, code: str) -> List[str]:
    """
    Scan AST for dangerous patterns.
    
    Args:
        tree: The AST tree of the tool source code.
        code: The raw source code string (checked for bypass comments).
        
    Returns:
        List[str]: A list of detected security violations.
    """
    if "# NOQA: SECURITY_RISK" in code:
        logger.warning("Security scan bypassed via NOQA: SECURITY_RISK")
        return []

    errors = []
    for node in ast.walk(tree):
        # Check imports
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in node.names]
            module = getattr(node, 'module', None)
            
            # Reject direct subprocess or os imports (unless specifically allowed)
            if "subprocess" in names or module == "subprocess":
                errors.append("Usage of 'subprocess' is restricted")
            
            # Check for dangerous os functions imported via 'from os import ...'
            dangerous_os = {'system', 'popen', 'spawn', 'execl', 'execle', 'execlp'}
            if module == "os" and any(name in dangerous_os for name in names):
                errors.append(f"Usage of dangerous 'os' functions is restricted: {', '.join(names)}")

        # Check calls
        if isinstance(node, ast.Call):
            # Check for os.system(), subprocess.run(), etc.
            if isinstance(node.func, ast.Attribute):
                attr = node.func.attr
                dangerous_os_calls = {'system', 'popen', 'spawn', 'execl', 'execle', 'execlp'}
                if attr in dangerous_os_calls:
                    errors.append(f"Usage of 'os.{attr}' (or similar) is restricted")
            
            # Check for eval(), exec(), compile()
            elif isinstance(node.func, ast.Name):
                if node.func.id in {'eval', 'exec', 'compile'}:
                    errors.append(f"Usage of '{node.func.id}' is forbidden")

    return errors


def import_tool(module_name: str, tool_path: Optional[Path] = None) -> str:
    """
    Imports or reloads a tool from the custom tools directory.

    When *tool_path* is supplied the module is loaded directly from that file
    (using ``importlib.util.spec_from_file_location``), which means the import
    succeeds regardless of whether the file lives inside the canonical
    ``agent.tools.custom`` package.  This makes the function testable with
    pytest's ``tmp_path`` fixture without polluting the real custom directory.

    When *tool_path* is omitted the legacy dotted-name import is used so that
    the public API stays backward-compatible.

    Args:
        module_name: The stem of the module (e.g., ``'my_tool'``).
        tool_path: Absolute path to the ``.py`` file, if known.

    Returns:
        str: Success message indicating whether the module was imported or reloaded.
    """
    full_module_path = f"agent.tools.custom.{module_name}"

    try:
        if tool_path is not None:
            # Path-based load — works with any directory (incl. tmp_path in tests).
            import importlib.util as _util
            spec = _util.spec_from_file_location(full_module_path, tool_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot create spec for {tool_path}")
            module = _util.module_from_spec(spec)
            if full_module_path in sys.modules:
                # Re-execute into the existing module object to hot-reload.
                spec.loader.exec_module(sys.modules[full_module_path])
                status = "Reloaded existing module."
            else:
                sys.modules[full_module_path] = module
                spec.loader.exec_module(module)
                status = "Imported new module."
        else:
            # Legacy dotted-name import (production path when file is in real custom/).
            if full_module_path in sys.modules:
                importlib.reload(sys.modules[full_module_path])
                status = "Reloaded existing module."
            else:
                importlib.import_module(full_module_path)
                status = "Imported new module."

        logger.info(
            f"Hot reload successful for {full_module_path}",
            extra={"module": full_module_path},
        )
        return status
    except Exception as e:
        logger.error(f"Hot reload failed for {full_module_path}: {e}")
        raise


def create_tool(file_path: str, code: str) -> str:
    """
    Creates a new tool file and hot-reloads it.
    
    Args:
        file_path: Relative path to the file within the custom tools directory.
        code: The Python source code for the tool.
        
    Returns:
        str: Success message with the file path and reload status.
        
    Raises:
        PathTraversalError: If the file_path attempts to escape the custom directory.
        SecurityError: If the code contains forbidden patterns.
        SyntaxError: If the code is not valid Python.
    """
    base_dir = _get_custom_tools_dir().resolve()
    
    # Path containment
    target_path = (base_dir / file_path).resolve()
    
    try:
        if not str(target_path).startswith(str(base_dir)):
            raise PathTraversalError(f"Security violation. Tools can only be created in {base_dir}.")
    except Exception:
        raise PathTraversalError("Security violation. Invalid path.")

    # Syntax Validation
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        logger.error(f"Syntax error in dynamic tool code: {e}")
        raise

    # Security Scan
    security_errors = _security_scan(tree, code)
    if security_errors:
        error_msg = f"Security Rejection: {'; '.join(security_errors)}. Add '# NOQA: SECURITY_RISK' to override."
        logger.error(error_msg)
        raise SecurityError(error_msg)

    # Write file
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(code)

        logger.warning(
            f"SECURITY: Dynamic tool created at {target_path}",
            extra={"path": str(target_path)},
        )

        # Hot Reload — pass the real file path so import_tool doesn't have to
        # guess the directory, keeping tests hermetic.
        module_name = target_path.stem
        reload_status = import_tool(module_name, tool_path=target_path)

        return f"Success: Tool created at {target_path}. {reload_status}"

    except Exception:
        logger.exception(f"Failed to create or reload tool at {target_path}")
        raise