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
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

@tool
def run_backend_tests(path: str = ".agent/tests/") -> str:
    """
    Run pytest on the backend codebase.
    Args:
        path: Test path (default: '.agent/tests/')
    """
    # Validation
    with tracer.start_as_current_span("tool.run_backend_tests") as span:
        if not os.path.exists(path):
            return f"Error: Test path '{path}' does not exist."
            
        try:
            # Security: Use list format for subprocess
            # Check if .venv exists, otherwise try system pytest
            cmd = [".venv/bin/pytest", path] if os.path.exists(".venv") else ["pytest", path]
            span.set_attribute("cmd", " ".join(cmd))
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                check=False 
            )
            output = result.stdout + result.stderr
            
            span.set_attribute("exit_code", result.returncode)
            
            # Add summary logic if output is huge
            if len(output) > 2000:
                summary = output.splitlines()[-5:] # Last 5 lines usually have summary
                return output[:2000] + "\n... (truncated)\n" + "\n".join(summary)
                
            return output
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR))
            return f"failed to run tests: {e}"

@tool
def run_frontend_lint() -> str:
    """
    Run linting on the frontend.
    """
    try:
        # Repo structure: .agent/src/web
        web_dir = ".agent/src/web"
        if not os.path.exists(web_dir):
            return "Web directory (.agent/src/web) not found."
            
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

@tool
def shell_command(command: str, cwd: str = ".") -> str:
    """
    Execute a shell command from the project root or a specific directory.
    Use this for package installation (npm install, pip install) or running utilities.
    Args:
        command: The shell command to run (e.g. 'ls -la', 'pip install requests')
        cwd: Working directory relative to project root (default: '.')
    """
    with tracer.start_as_current_span("tool.shell_command") as span:
        span.set_attribute("command", command)
        span.set_attribute("cwd", cwd)
        try:
            # Security: Prevent escaping project root if possible
            # Resolve CWD to absolute path, defaulting to Repo Root if "."
            if cwd == ".":
                cwd = os.getcwd()
            
            if ".." in cwd or (cwd.startswith("/") and not cwd.startswith(os.getcwd())):
                return "Error: Working directory must be within project root."
            
            # We will split the command into a list safely
            import shlex
            cmd_args = shlex.split(command)
            
            result = subprocess.run(
                cmd_args,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False
            )
            
            output = result.stdout + result.stderr
            span.set_attribute("exit_code", result.returncode)
            
            if len(output) > 5000:
                 return output[:5000] + "\n... (truncated)"
            return output
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR))
            return f"Error executing shell command: {e}"
