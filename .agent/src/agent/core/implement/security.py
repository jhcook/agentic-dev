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

"""Security and sanitization utilities for the implementation domain (INFRA-169)."""

import logging
from typing import Any
from agent.core.utils import scrub_sensitive_data

class OrchestrationSecurityFilter(logging.Filter):
    """Logging filter that scrubs sensitive data from all implementation log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filters log records to remove sensitive information from messages and arguments.

        Args:
            record: The log record to process.

        Returns:
            Always True to allow the record to be logged after scrubbing.
        """
        if isinstance(record.msg, str):
            record.msg = scrub_sensitive_data(record.msg)
        
        if record.args:
            new_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    new_args.append(scrub_sensitive_data(arg))
                else:
                    new_args.append(arg)
            record.args = tuple(new_args)
        
        return True

def sanitize_error_message(error: Exception) -> str:
    """
    Extracts and scrubs the message from an exception for safe use in UI or logs.

    Args:
        error: The exception to sanitize.

    Returns:
        The scrubbed exception string.
    """
    return scrub_sensitive_data(str(error))

def apply_orchestration_filter(logger_name: str = "agent.core.implement") -> None:
    """
    Hooks the security filter into the specified logger if not already present.

    Args:
        logger_name: The name of the logger to secure.
    """
    target_logger = logging.getLogger(logger_name)
    # Check if filter already exists to prevent duplication
    for f in target_logger.filters:
        if isinstance(f, OrchestrationSecurityFilter):
            return
    target_logger.addFilter(OrchestrationSecurityFilter())
