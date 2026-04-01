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
Context management tools for checkpointing and rolling back file edits.
"""

import subprocess
from pathlib import Path
from agent.core.utils import logger
from typing import Any, Dict, Optional
from agent.core.governance.audit_handler import audit_tool
from agent.tools.interfaces import ContextToolResult
from agent.utils.tool_security import sanitize_and_validate_args

@audit_tool(domain="context", action="checkpoint")
def checkpoint(message: str = "agent_checkpoint", repo_root: Optional[Path] = None) -> ContextToolResult:
    """
    Snapshots the current working tree using git stash.

    Args:
        message: Metadata for the checkpoint.
        repo_root: Repository root.
    """
    try:
        # Ensure we are in a git repo
        subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_root, check=True, capture_output=True)

        # Push to stash with message
        # We use --include-untracked to ensure new files are saved
        cmd = sanitize_and_validate_args(["git", "stash", "push", "--include-untracked", "-m", f"CHECKPOINT:{message}"])
        res = subprocess.run(
            cmd,
            cwd=repo_root, capture_output=True, text=True
        )

        # If there were no local changes, stash push emits "No local changes to save"
        # and creates no stash entry. Treat this as a successful no-op checkpoint.
        if "No local changes to save" in (res.stdout + res.stderr):
            return {"success": True, "output": "Checkpoint created (working tree was clean — no changes to stash)."}

        # Since stash push clears the worktree, we apply it immediately back
        # so the agent can keep working, but we now have a restorable state.
        subprocess.run(["git", "stash", "apply", "stash@{0}"], cwd=repo_root, check=True, capture_output=True)

        return {"success": True, "output": "Checkpoint created and applied to working tree."}
    except Exception as e:
        return {"success": False, "error": f"Checkpoint failed: {str(e)}"}

@audit_tool(domain="context", action="rollback")
def rollback(repo_root: Optional[Path] = None) -> ContextToolResult:
    """
    Restores the working tree to the state of the last CHECKPOINT stash.
    """
    try:
        # List stashes to find the latest CHECKPOINT
        list_res = subprocess.run(
            ["git", "stash", "list"], 
            cwd=repo_root, capture_output=True, text=True, check=True
        )
        
        if "CHECKPOINT:" not in list_res.stdout:
            return {"success": False, "error": "No checkpoint found in git stash."}

        # Find the index of the latest CHECKPOINT
        stash_idx = None
        for line in list_res.stdout.splitlines():
            if "CHECKPOINT:" in line:
                stash_idx = line.split(":")[0].strip()
                break

        if stash_idx is None:
             return {"success": False, "error": "No valid checkpoint found."}

        # Hard reset tracked files and clean all untracked files/dirs
        subprocess.run(["git", "reset", "--hard"], cwd=repo_root, check=True, capture_output=True)
        subprocess.run(["git", "clean", "-fd"], cwd=repo_root, check=True, capture_output=True)
        subprocess.run(["git", "stash", "apply", stash_idx], cwd=repo_root, check=True, capture_output=True)

        return {"success": True, "output": f"Rolled back to {stash_idx}."}
    except Exception as e:
        return {"success": False, "error": f"Rollback failed: {str(e)}"}

@audit_tool(domain="context", action="summarize_changes")
def summarize_changes(repo_root: Optional[Path] = None) -> ContextToolResult:
    """
    Generates a diff of the current working tree against the git index.
    """
    try:
        result = subprocess.run(["git", "diff"], cwd=repo_root, capture_output=True, text=True)
        return {"success": True, "output": result.stdout or "No changes detected."}
    except Exception as e:
        return {"success": False, "error": str(e)}
