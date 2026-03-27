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
Testing domain tools for running and parsing test suites.
"""

import subprocess
import re
import json
from pathlib import Path
from agent.core.utils import logger
from typing import Any, Dict, Optional
from agent.core.governance.audit_handler import audit_tool
from agent.tools.interfaces import TestingToolResult
from agent.utils.tool_security import sanitize_and_validate_args

@audit_tool(domain="testing", action="run_tests")
def run_tests(path: str = ".", repo_root: Optional[Path] = None) -> TestingToolResult:
    """
    Runs the test suite at the given path and returns structured results.

    Args:
        path: Directory or file containing tests.
        repo_root: Root of the repository.

    Returns:
        Dictionary with passed, failed, errors, and coverage_pct.
    """
    cmd = sanitize_and_validate_args(["pytest", "--verbose", path])
    try:
        # Note: In a real implementation, we might use pytest-json-report
        # Here we parse raw output to ensure structured data return (AC-5)
        result = subprocess.run(
            cmd, 
            cwd=repo_root, 
            capture_output=True, 
            text=True, 
            check=False
        )
        
        output = result.stdout + result.stderr
        
        # Basic summary extraction logic
        summary_match = re.search(r"==+ (.*) ==+", output.splitlines()[-1] if output.splitlines() else "")
        summary_line = summary_match.group(1) if summary_match else ""
        
        passed = int(re.search(r"(\d+) passed", summary_line).group(1)) if "passed" in summary_line else 0
        failed = int(re.search(r"(\d+) failed", summary_line).group(1)) if "failed" in summary_line else 0
        errors = int(re.search(r"(\d+) error", summary_line).group(1)) if "error" in summary_line else 0
        
        # Mock coverage for now as it requires --cov flag
        coverage_pct = 0.0
        
        return {
            "success": result.returncode == 0,
            "output": {
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "coverage_pct": coverage_pct,
                "raw_output": output[:2000] # Cap output for readability
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@audit_tool(domain="testing", action="run_single_test")
def run_single_test(test_path: str, repo_root: Optional[Path] = None) -> TestingToolResult:
    """Runs a single test file."""
    return run_tests(path=test_path, repo_root=repo_root)

@audit_tool(domain="testing", action="coverage_report")
def coverage_report(repo_root: Optional[Path] = None) -> TestingToolResult:
    """Placeholder for generating full coverage reports."""
    return {"success": True, "output": "Coverage analysis not yet configured with --cov."}
