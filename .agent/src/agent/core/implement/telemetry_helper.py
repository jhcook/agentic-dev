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

"""telemetry_helper module."""

# Copyright 2026 Justin Cook

import os
import time
from typing import Any, Dict, Optional
from agent.core.logger import get_logger

_logger = get_logger(__name__)

def log_assembly_audit(user: str, template_version: str, block_count: int, success: bool, duration_ms: float):
    """Log a structured audit event for runbook assembly.

    Args:
        user: The identity of the user who triggered the assembly.
        template_version: The version string of the skeleton template used.
        block_count: Number of blocks processed during assembly.
        success: Whether the assembly completed without errors.
        duration_ms: Time taken to assemble in milliseconds.
    """
    _logger.info(
        "runbook_assembly_audit",
        extra={
            "audit": {
                "event": "assembly",
                "user": user,
                "template_version": template_version,
                "block_count": block_count,
                "status": "success" if success else "failure",
                "latency_ms": duration_ms
            }
        }
    )

def calculate_block_density(block_count: int, content: str) -> float:
    """Calculate the mapping density (blocks per 100 lines).

    Args:
        block_count: Number of addressable blocks found.
        content: The raw source content.

    Returns:
        Density percentage as a float.
    """
    lines = len(content.splitlines())
    if lines == 0:
        return 0.0
    return (block_count / lines) * 100
