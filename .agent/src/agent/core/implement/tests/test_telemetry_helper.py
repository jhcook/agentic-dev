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

"""Tests for orchestration telemetry hooks (INFRA-169)."""

import logging
import pytest
from agent.core.implement.telemetry_helper import emit_chunk_event


class MockHandler(logging.Handler):
    """Mock handler to capture log records."""

    def __init__(self):
        """Initialise with an empty records list."""
        super().__init__()
        self.records = []

    def emit(self, record):
        """Capture the log record."""
        self.records.append(record)


@pytest.fixture
def log_capture():
    """Attach a mock handler to the telemetry logger and yield it."""
    logger = logging.getLogger("agent.core.implement.telemetry")
    logger.setLevel(logging.DEBUG)
    handler = MockHandler()
    logger.addHandler(handler)
    yield handler
    logger.removeHandler(handler)


def test_emit_chunk_start(log_capture):
    """Verify chunk_start events are logged at INFO level."""
    emit_chunk_event("chunk_start", "INFRA-169", 1)
    assert len(log_capture.records) == 1
    assert log_capture.records[0].msg == "chunk_start story=INFRA-169 step=1"


def test_emit_chunk_success_with_metrics(log_capture):
    """Verify chunk_success events include duration and file metadata."""
    emit_chunk_event(
        "chunk_success",
        "INFRA-169",
        1,
        duration=0.555,
        modified_files=["file1.py"],
    )
    assert len(log_capture.records) == 1
    record = log_capture.records[0]
    # extra dict keys are merged into the record namespace
    assert record.duration_ms == 555.0
    assert record.files == ["file1.py"]


def test_emit_chunk_failure_log_level(log_capture):
    """Verify chunk_failure events are logged at ERROR level."""
    emit_chunk_event("chunk_failure", "INFRA-169", 1, error="Timeout")
    assert log_capture.records[0].levelno == logging.ERROR
    assert log_capture.records[0].error == "Timeout"
