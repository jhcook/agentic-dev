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
import subprocess
import os

@tool
def run_backend_tests(path: str = "tests/") -> str:
    """
    Run pytest on the backend codebase.
    Args:
        path: Test path (default: 'tests/')
    """
    # Validation
    if not os.path.exists(path):
        return f"Error: Test path '{path}' does not exist."
        
    try:
        # Security: Use list format for subprocess
        # Check if .venv exists, otherwise try system pytest
        cmd = [".venv/bin/pytest", path] if os.path.exists(".venv") else ["pytest", path]
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True,
            check=False 
        )
        output = result.stdout + result.stderr
        
        # Add summary logic if output is huge
        if len(output) > 2000:
            summary = output.splitlines()[-5:] # Last 5 lines usually have summary
            return output[:2000] + "\n... (truncated)\n" + "\n".join(summary)
            
        return output
    except Exception as e:
        return f"failed to run tests: {e}"

@tool
def run_frontend_lint() -> str:
    """
    Run linting on the frontend.
    """
    try:
        # Repo structure: .agent/web
        web_dir = ".agent/web"
        if not os.path.exists(web_dir):
            return "Web directory (.agent/web) not found."
            
        result = subprocess.run(
            ["npm", "run", "lint"], 
            cwd=web_dir,
            capture_output=True, 
            text=True,
            check=False
        )
        output = result.stdout + result.stderr
        if len(output) > 2000:
            return output[:2000] + "\n... (truncated)"
        return output
    except Exception as e:
        return f"Error: {e}"
