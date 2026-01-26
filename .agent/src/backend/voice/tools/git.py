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
import logging

logger = logging.getLogger(__name__)

@tool
def get_git_status() -> str:
    """
    Get the current git status of the repository.
    Useful for checking what files have changed or are untracked.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--short"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        return result.stdout or "Working tree clean."
    except subprocess.CalledProcessError as e:
        return f"Error checking git status: {e}"

@tool
def get_git_diff() -> str:
    """
    Get the staged git diff. 
    Use this during preflight checks to see what is about to be committed.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        if not result.stdout:
            return "No staged changes."
        # Truncate if too long (LLM context limit)
        if len(result.stdout) > 5000:
            return result.stdout[:5000] + "\n...[Truncated]"
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error checking git diff: {e}"

@tool
def get_git_log(limit: int = 5) -> str:
    """
    Get the recent git log history.
    Args:
        limit: Number of commits to show (default: 5)
    """
    try:
        result = subprocess.run(
            ["git", "log", f"-n {limit}", "--oneline"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error getting git log: {e}"
@tool
def get_git_branch() -> str:
    """
    Get the current active git branch name.
    Useful for inferring the current story or task context.
    """
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        return result.stdout.strip() or "HEAD (detached)"
    except subprocess.CalledProcessError as e:
        return f"Error getting git branch: {e}"
