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

"""Tests for implementation-layer security and sanitization (INFRA-169)."""

import logging
import pytest
from agent.core.implement.security import OrchestrationSecurityFilter, sanitize_error_message


def test_sanitize_error_message_scrubs_openai_key():
    """Verify that OpenAI-format API keys in exception messages are scrubbed."""
    fake_error = ValueError(
        "Connection failed for key: sk-abcdefghijklmnopqrstuvwxyz1234567890"
    )
    scrubbed = sanitize_error_message(fake_error)
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in scrubbed
    assert "[REDACTED:OPENAI_KEY]" in scrubbed


def test_orchestration_filter_scrubs_log_args():
    """Verify the logging filter scrubs sensitive strings passed as log arguments."""
    logger = logging.getLogger("test.orchestration.security")
    logger.setLevel(logging.DEBUG)
    logger.addFilter(OrchestrationSecurityFilter())

    class CapturingHandler(logging.Handler):
        """Mock handler to capture log records."""

        def __init__(self):
            """Initialise with an empty records list."""
            super().__init__()
            self.records = []

        def emit(self, record):
            """Capture the log record."""
            self.records.append(record)

    handler = CapturingHandler()
    logger.addHandler(handler)

    # Use an OpenAI-style key that the regex will match (sk- + 20 alphanumeric)
    logger.warning(
        "Retry attempt failed with error: %s",
        "sk-abcdefghijklmnopqrstuvwxyz",
    )

    assert len(handler.records) == 1
    logged_arg = handler.records[0].args[0]
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in logged_arg
    assert "[REDACTED:OPENAI_KEY]" in logged_arg


def test_orchestration_filter_preserves_non_sensitive_args():
    """Verify the logging filter does not mangle non-string, non-sensitive arguments."""
    logger = logging.getLogger("test.orchestration.safe")
    logger.setLevel(logging.DEBUG)
    logger.addFilter(OrchestrationSecurityFilter())

    class CapturingHandler(logging.Handler):
        """Mock handler to capture log records."""

        def __init__(self):
            """Initialise with an empty records list."""
            super().__init__()
            self.records = []

        def emit(self, record):
            """Capture the log record."""
            self.records.append(record)

    handler = CapturingHandler()
    logger.addHandler(handler)

    logger.info("Processing chunk %d of %d", 1, 5)

    assert handler.records[0].args == (1, 5)
