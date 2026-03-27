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

"""Orchestration logic for implementing runbook steps (INFRA-170)."""

import subprocess
import logging
from typing import List, Optional
from pathlib import Path
from agent.core.config import config

logger = logging.getLogger(__name__)

def micro_commit_step(
    story_id: str,
    step_index: int,
    step_loc: int,
    cumulative_loc: int,
    modified_files: List[str],
) -> bool:
    """Stage and commit modified files as an atomic save-point."""
    if not modified_files:
        return True
    try:
        subprocess.run(
            ["git", "add", "--"] + modified_files,
            check=True, capture_output=True, timeout=30,
        )
        msg = (
            f"feat({story_id}): implement step {step_index} "
            f"[{step_loc} LOC, {cumulative_loc} cumulative]"
        )
        subprocess.run(
            ["git", "commit", "-m", msg],
            check=True, capture_output=True, timeout=30,
        )
        return True
    except subprocess.CalledProcessError as e:
        logger.warning("Micro-commit failed for %s step %d: %s", story_id, step_index, e)
        return False

def check_git_hygiene(story_id: str, allow_dirty: bool) -> None:
    """Verify git state before implementation."""
    from agent.core.utils import is_git_dirty
    if not allow_dirty and is_git_dirty():
        raise RuntimeError(
            "Uncommitted changes detected. Commit or stash before implementing, or use --allow-dirty."
        )
