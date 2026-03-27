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

"""
Dependency management tools wrapping uv and pip-audit.
"""

import subprocess
from pathlib import Path
from agent.core.utils import logger
from typing import Any, Dict, Optional
import json
from agent.core.governance.audit_handler import audit_tool
from agent.tools.interfaces import DepsToolResult, AuditDependencyResult, AuditVulnerability
from agent.utils.tool_security import sanitize_and_validate_args

@audit_tool(domain="deps", action="add_dependency")
def add_dependency(package: str, repo_root: Optional[Path] = None) -> DepsToolResult:
    """
    Adds a dependency using `uv add`.

    Args:
        package: Package name to add.
        repo_root: Repository root.
    """
    try:
        cmd = sanitize_and_validate_args(["uv", "add", package])
        result = subprocess.run(
            cmd, 
            cwd=repo_root, 
            capture_output=True, 
            text=True
        )
        return {
            "success": result.returncode == 0,
            "output": result.stdout if result.returncode == 0 else result.stderr
        }
    except FileNotFoundError:
        return {"success": False, "error": "'uv' command not found. Please install uv."}

@audit_tool(domain="deps", action="audit_dependencies")
def audit_dependencies(repo_root: Optional[Path] = None) -> DepsToolResult:
    """
    Audits dependencies for vulnerabilities using pip-audit.
    """
    try:
        result = subprocess.run(
            ["pip-audit", "--format", "json"], 
            cwd=repo_root, 
            capture_output=True, 
            text=True
        )
        parsed_output = json.loads(result.stdout) if result.stdout else []
        typed_output: list[AuditDependencyResult] = []
        for item in parsed_output:
            vulns: list[AuditVulnerability] = []
            for v in item.get("vulns", []):
                vulns.append({
                    "id": v.get("id", ""),
                    "fix_versions": v.get("fix_versions", []),
                    "aliases": v.get("aliases", []),
                    "description": v.get("description", "")
                })
            typed_output.append({
                "name": item.get("name", ""),
                "version": item.get("version", ""),
                "vulns": vulns
            })
        return {
            "success": result.returncode == 0,
            "output": typed_output
        }
    except Exception as e:
        return {"success": False, "error": f"Audit failed: {str(e)}"}

@audit_tool(domain="deps", action="list_outdated")
def list_outdated(repo_root: Optional[Path] = None) -> DepsToolResult:
    """Lists outdated dependencies via uv."""
    try:
        result = subprocess.run(
            ["uv", "pip", "list", "--outdated"], 
            cwd=repo_root, 
            capture_output=True, 
            text=True
        )
        return {"success": True, "output": result.stdout}
    except Exception as e:
        return {"success": False, "error": str(e)}
