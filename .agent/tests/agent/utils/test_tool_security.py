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

"""Unit tests for tool security and sanitization utilities."""

import pytest
from pathlib import Path
from agent.utils.tool_security import validate_safe_path, sanitize_vector_query


def test_validate_safe_path_allowed(tmp_path):
    """Verify that valid paths within the base directory are accepted."""
    base = tmp_path / "project"
    base.mkdir()
    target_file = base / "stories" / "STORY-001.md"
    target_file.parent.mkdir()
    target_file.write_text("content")

    resolved = validate_safe_path("stories/STORY-001.md", base)
    assert resolved == target_file.resolve()


def test_validate_safe_path_traversal_denied(tmp_path):
    """Verify that directory traversal attempts raise ValueError."""
    base = tmp_path / "root"
    base.mkdir()
    (tmp_path / "secret.txt").write_text("secret data")

    with pytest.raises(ValueError, match="Security Violation"):
        validate_safe_path("../secret.txt", base)


def test_validate_safe_path_absolute_outside_denied(tmp_path):
    """Verify that absolute paths outside the root are denied."""
    base = tmp_path / "root"
    base.mkdir()

    with pytest.raises(ValueError, match="Security Violation"):
        validate_safe_path("/etc/passwd", base)


def test_sanitize_vector_query_cleaning():
    """Verify removal of control characters and excessive whitespace."""
    raw_query = "Find ADRs about auth\n\r\t"
    assert sanitize_vector_query(raw_query) == "Find ADRs about auth"


def test_sanitize_vector_query_length():
    """Verify that long queries are truncated to the max_length."""
    long_input = "a" * 1000
    sanitized = sanitize_vector_query(long_input, max_length=100)
    assert len(sanitized) == 100


def test_sanitize_vector_query_empty():
    """Verify handling of empty or None input."""
    assert sanitize_vector_query("") == ""
    assert sanitize_vector_query(None) == ""
