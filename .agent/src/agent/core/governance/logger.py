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

"""Audit logging utilities for governance gate violations (INFRA-170)."""

import logging
from typing import Optional
from agent.core.governance import log_governance_event

logger = logging.getLogger(__name__)

def log_complexity_violation(
    file_path: str,
    metric: str,
    value: int,
    threshold: int,
    verdict: str,
    function_name: Optional[str] = None
) -> None:
    """Log a code complexity violation to the internal audit log.

    Args:
        file_path: The repository-relative path to the violating file.
        metric: The name of the complexity metric (e.g., 'LOC', 'Function Length').
        value: The actual measured value.
        threshold: The threshold defined in ADR-012.
        verdict: The resulting gate verdict ('WARN' or 'BLOCK').
        function_name: Optional name of the violating function or method.
    """
    # Map verdict to event types used in audit_events.log
    event_type = f"GATE_VIOLATION_{verdict}"
    
    # Construct structured details string for the audit log
    details = f"file={file_path} metric='{metric}' value={value} limit={threshold}"
    if function_name:
        details += f" function='{function_name}'"

    # Capture in the internal governance audit log using the core provider
    log_governance_event(
        event_type=event_type,
        details=details
    )

    # Also mirror to standard logging for immediate visibility in verbose mode
    log_msg = f"Complexity Gate {verdict}: {details}"
    if verdict == "BLOCK":
        logger.error(log_msg)
    else:
        logger.warning(log_msg)
