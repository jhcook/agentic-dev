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
from agent.core.config import config as agent_config
import subprocess

@tool
def get_recent_logs(lines: int = 50) -> str:
    """
    Get the most recent lines from the agent log file (agent.log).
    """
    # Use absolute path based on repo_root
    # Check standard locations
    possible_paths = [
        agent_config.repo_root / "agent.log",
        agent_config.agent_dir / "agent.log",
        agent_config.agent_dir / "logs" / "agent.log"
    ]
    
    log_file = None
    for p in possible_paths:
        if p.exists():
            log_file = str(p)
            break
            
    if not log_file:
         return "Log file not found."
        
    try:
        # Use tail command for efficiency on Mac/Linux
        # Security: lines is int so safe to cast
        params = ["tail", "-n", str(lines), log_file]
        res = subprocess.run(
            params, 
            capture_output=True, 
            text=True,
            cwd=str(agent_config.repo_root)
        )
        return res.stdout
    except Exception as e:
        return f"Error reading logs: {e}"
