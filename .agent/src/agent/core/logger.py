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

import logging

# Configure default logging (Default to WARNING to be quiet)
# We do NOT call basicConfig here to avoid side effects on import.
# Instead, we provide a setup function.

# Guard flag to prevent adding duplicate file handlers.
_file_handler_added = False


def configure_logging(verbosity: int = 0):
    """
    Configure logging based on verbosity level.
    0 = WARNING (default)
    1 = INFO (-v)
    2 = DEBUG (Agent DEBUG, Libraries WARNING) (-vv)
    3 = DEBUG (Full DEBUG) (-vvv)
    """
    # Default: Root WARNING
    root_level = logging.WARNING
    agent_level = logging.WARNING
    
    if verbosity == 1:
        # -v: Agent INFO, Root WARNING
        agent_level = logging.INFO
    elif verbosity == 2:
        # -vv: Agent DEBUG, Root WARNING (keep libraries quiet)
        agent_level = logging.DEBUG
        root_level = logging.WARNING
    elif verbosity >= 3:
        # -vvv: Everything DEBUG
        agent_level = logging.DEBUG
        root_level = logging.DEBUG

    # Remove existing handlers to avoid duplicates
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            root.removeHandler(handler)

    logging.basicConfig(
        level=root_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
             logging.StreamHandler()
        ]
    )
    
    # Set Agent level explicitly if different from root
    logging.getLogger("agent").setLevel(agent_level)

    # Lazy file handler: create logs dir and attach handler only when
    # configure_logging is called AND the .agent project directory exists.
    global _file_handler_added
    if not _file_handler_added:
        from agent.core.config import config
        if config.agent_dir.exists():
            log_dir = config.logs_dir
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_dir / "agent.log")
            file_handler.setFormatter(
                logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            )
            logging.getLogger("agent").addHandler(file_handler)
            _file_handler_added = True

# Create a custom logger (no file handler at import time)
logger = logging.getLogger("agent")

def get_logger(name: str):
    """Get a logger instance with the specified name."""
    return logging.getLogger(f"agent.{name}")
